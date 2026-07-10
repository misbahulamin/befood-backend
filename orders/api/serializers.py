from rest_framework import serializers

from meals.models import MealCategory
from orders.models import Order
from orders.services.order_service import (
    InactiveMealError,
    MonthLockError,
    create_meal_order,
)
from user_management.models import CustomerProfile


class OrderCreateSerializer(serializers.Serializer):
    meal_id = serializers.IntegerField()
    customer_note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_meal_id(self, value):
        try:
            meal = MealCategory.objects.get(pk=value)
        except MealCategory.DoesNotExist:
            raise serializers.ValidationError('Meal not found.')
        if not meal.is_active:
            raise serializers.ValidationError('This meal package is not available for ordering.')
        self.context['meal'] = meal
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        profile = getattr(user, 'customer_profile', None)
        if profile is None:
            raise serializers.ValidationError('Customer profile is required to place an order.')
        if not profile.is_email_verified:
            raise serializers.ValidationError('Email verification is required before placing an order.')
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        customer = user.customer_profile
        meal = self.context['meal']
        try:
            return create_meal_order(
                customer=customer,
                meal=meal,
                customer_note=validated_data.get('customer_note', ''),
            )
        except MonthLockError as exc:
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
        except InactiveMealError as exc:
            raise serializers.ValidationError({'meal_id': [str(exc)]})


class OrderListSerializer(serializers.ModelSerializer):
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    meal_type_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id',
            'meal',
            'meal_name_snapshot',
            'meal_type_snapshot',
            'meal_type_display',
            'total_price_snapshot',
            'per_meal_price_snapshot',
            'order_status',
            'order_status_display',
            'order_start_date',
            'order_end_date',
            'service_days_count',
            'order_month',
            'customer_note',
            'created_at',
            'updated_at',
        )

    def get_meal_type_display(self, obj):
        return dict(MealCategory.MealType.choices).get(obj.meal_type_snapshot, obj.meal_type_snapshot)


class OrderDetailSerializer(OrderListSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ('customer',)


class OrderCancelSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default='')
