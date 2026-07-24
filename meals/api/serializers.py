from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from meals.models import MealCategory
from meals.services.meal_image import validate_image_extension, validate_image_size
from meals.services.meal_offering import (
    build_public_cycle_offering,
    get_latest_finalized_plan,
    resolve_public_per_meal_price,
)


class MealListSerializer(serializers.ModelSerializer):
    meal_thumbnail = serializers.SerializerMethodField()
    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)
    meal_period_display = serializers.CharField(source='get_meal_period_display', read_only=True)
    per_meal_price = serializers.SerializerMethodField()
    pricing_status = serializers.CharField(read_only=True)

    class Meta:
        model = MealCategory
        fields = (
            'public_id',
            'meal_name',
            'total_price',
            'per_meal_price',
            'pricing_status',
            'meal_thumbnail',
            'meal_type',
            'meal_type_display',
            'meal_period',
            'meal_period_display',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_per_meal_price(self, obj):
        return resolve_public_per_meal_price(obj)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_meal_thumbnail(self, obj):
        if not obj.meal_thumbnail:
            return None
        request = self.context.get('request')
        url = obj.meal_thumbnail.url
        return request.build_absolute_uri(url) if request else url


class MealDetailSerializer(MealListSerializer):
    current_cycle_offering = serializers.SerializerMethodField()

    class Meta(MealListSerializer.Meta):
        fields = MealListSerializer.Meta.fields + ('description', 'current_cycle_offering')

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_current_cycle_offering(self, obj):
        plan = get_latest_finalized_plan(obj)
        if plan is None:
            return None
        return build_public_cycle_offering(plan)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_per_meal_price(self, obj):
        plan = get_latest_finalized_plan(obj)
        return resolve_public_per_meal_price(obj, offering_plan=plan)


class MealCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCategory
        fields = (
            'meal_name',
            'meal_thumbnail',
            'meal_type',
            'meal_period',
            'description',
            'is_active',
        )
        extra_kwargs = {
            'meal_period': {'required': True},
        }

    def validate_meal_type(self, value):
        valid_values = {choice.value for choice in MealCategory.MealType}
        if value not in valid_values:
            raise serializers.ValidationError(
                f'Invalid meal type. Allowed values: {", ".join(sorted(valid_values))}.'
            )
        return value

    def validate_meal_period(self, value):
        valid_values = {choice.value for choice in MealCategory.MealPeriod}
        if value not in valid_values:
            raise serializers.ValidationError(
                f'Invalid meal period. Allowed values: {", ".join(sorted(valid_values))}.'
            )
        return value

    def validate_meal_thumbnail(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, attrs):
        thumbnail = attrs.get('meal_thumbnail')
        if self.instance is None and not thumbnail:
            raise serializers.ValidationError({'meal_thumbnail': 'Meal thumbnail is required.'})
        if self.instance is None and not attrs.get('meal_period'):
            raise serializers.ValidationError({'meal_period': 'Meal period is required.'})
        return attrs

    def create(self, validated_data):
        validated_data['total_price'] = None
        return super().create(validated_data)
