from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from meals.models import OperationalCostItem, OperationalCostMonth
from meals.services.operational_cost import month_cost_breakdown
from meals.services.operational_cost_items import replace_operational_cost_items


class OperationalCostItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalCostItem
        fields = (
            'id',
            'public_id',
            'name',
            'amount',
            'notes',
            'sort_order',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'public_id', 'created_at', 'updated_at')

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Item name is required.')
        return cleaned

    def validate_amount(self, value: Decimal) -> Decimal:
        if value is None or value < Decimal('0'):
            raise serializers.ValidationError('Amount must be 0 or greater.')
        return value


class OperationalCostItemWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    sort_order = serializers.IntegerField(required=False, min_value=0)


class OperationalCostItemBulkSerializer(serializers.Serializer):
    items = OperationalCostItemWriteSerializer(many=True)


class OperationalCostMonthSerializer(serializers.ModelSerializer):
    items = OperationalCostItemSerializer(many=True, read_only=True)
    total_operational_cost = serializers.SerializerMethodField()
    per_meal_operational_cost = serializers.SerializerMethodField()
    items_payload = OperationalCostItemWriteSerializer(
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model = OperationalCostMonth
        fields = (
            'id',
            'public_id',
            'year',
            'month',
            'target_meal_quantity',
            'notes',
            'items',
            'items_payload',
            'total_operational_cost',
            'per_meal_operational_cost',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'public_id',
            'items',
            'total_operational_cost',
            'per_meal_operational_cost',
            'created_at',
            'updated_at',
        )

    def validate_year(self, value: int) -> int:
        if value < 2000 or value > 2100:
            raise serializers.ValidationError('Year must be between 2000 and 2100.')
        return value

    def validate_month(self, value: int) -> int:
        if value < 1 or value > 12:
            raise serializers.ValidationError('Month must be between 1 and 12.')
        return value

    def validate_target_meal_quantity(self, value: int) -> int:
        if value is None or value <= 0:
            raise serializers.ValidationError('target_meal_quantity must be greater than 0.')
        return value

    def validate(self, attrs):
        year = attrs.get('year') or getattr(self.instance, 'year', None)
        month = attrs.get('month') or getattr(self.instance, 'month', None)
        if year and month:
            qs = OperationalCostMonth.objects.filter(year=year, month=month)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'month': 'An operational cost month already exists for this year and month.'}
                )
        return attrs

    @extend_schema_field(serializers.CharField())
    def get_total_operational_cost(self, obj: OperationalCostMonth) -> str:
        return str(month_cost_breakdown(obj)['total_operational_cost'])

    @extend_schema_field(serializers.CharField())
    def get_per_meal_operational_cost(self, obj: OperationalCostMonth) -> str:
        return str(month_cost_breakdown(obj)['per_meal_operational_cost'])

    def create(self, validated_data):
        items_payload = validated_data.pop('items_payload', None) or []
        month = OperationalCostMonth.objects.create(**validated_data)
        if items_payload:
            replace_operational_cost_items(month, items_payload)
        return month

    def update(self, instance, validated_data):
        items_payload = validated_data.pop('items_payload', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_payload is not None:
            replace_operational_cost_items(instance, items_payload)
        return instance
