from rest_framework import serializers

from decimal import Decimal, InvalidOperation

from meals.models import MealCategory
from orders.models import MealOffSettings, Order, OrderDelivery, OrderWalletSettings
from orders.services.meal_off import can_meal_off, meal_off_deadline
from orders.services.order_delivery import get_order_progress
from orders.services.order_service import (
    FrozenWalletOrderError,
    InactiveMealError,
    InsufficientWalletBalanceError,
    MonthLockError,
    UnpricedMealError,
    create_meal_order,
)


class OrderCreateSerializer(serializers.Serializer):
    meal_public_id = serializers.UUIDField()
    customer_note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_meal_public_id(self, value):
        try:
            meal = MealCategory.objects.get(public_id=value)
        except MealCategory.DoesNotExist:
            raise serializers.ValidationError('Meal not found.')
        if not meal.is_active:
            raise serializers.ValidationError('This meal package is not available for ordering.')
        if meal.total_price is None:
            raise serializers.ValidationError(
                'This meal package has no published price yet. Finalize a cycle plan first.'
            )
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
        except (InsufficientWalletBalanceError, FrozenWalletOrderError) as exc:
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
        except InactiveMealError as exc:
            raise serializers.ValidationError({'meal_public_id': [str(exc)]})
        except UnpricedMealError as exc:
            raise serializers.ValidationError({'meal_public_id': [str(exc)]})


class OrderProgressMixin:
    def _progress(self, obj):
        cache = self.context.setdefault('_order_progress_cache', {})
        if obj.pk not in cache:
            cache[obj.pk] = get_order_progress(obj)
        return cache[obj.pk]

    def get_expected_deliveries(self, obj):
        return self._progress(obj)['expected_deliveries']

    def get_delivered_count(self, obj):
        return self._progress(obj)['delivered_count']

    def get_remaining_count(self, obj):
        return self._progress(obj)['remaining_count']

    def get_active_days_this_month(self, obj):
        return self._progress(obj)['active_days_this_month']


class OrderDeliverySerializer(serializers.ModelSerializer):
    can_meal_off = serializers.SerializerMethodField()
    meal_off_deadline_at = serializers.SerializerMethodField()

    class Meta:
        model = OrderDelivery
        fields = (
            'public_id',
            'service_date',
            'meal_period',
            'status',
            'skip_source',
            'can_meal_off',
            'meal_off_deadline_at',
            'delivery_label_snapshot',
            'delivery_full_address_snapshot',
            'delivery_area_snapshot',
            'delivery_city_snapshot',
            'delivery_latitude_snapshot',
            'delivery_longitude_snapshot',
            'marked_by',
            'marked_at',
            'note',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_can_meal_off(self, obj):
        return can_meal_off(obj)

    def get_meal_off_deadline_at(self, obj):
        try:
            deadline = meal_off_deadline(obj.service_date, obj.meal_period)
        except ValueError:
            return None
        return deadline.isoformat().replace('+00:00', 'Z')


class MealOffRequestSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default='')


class MealOffSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealOffSettings
        fields = (
            'timezone',
            'lunch_off_time',
            'dinner_off_time',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(f'Unknown timezone: {value}') from exc
        return value


class OrderWalletSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderWalletSettings
        fields = (
            'min_wallet_balance_to_order',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_min_wallet_balance_to_order(self, value):
        try:
            amount = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise serializers.ValidationError('Amount must be a valid decimal number.') from exc
        if amount < 0:
            raise serializers.ValidationError('Amount must be greater than or equal to zero.')
        if amount.as_tuple().exponent < -2:
            raise serializers.ValidationError('Amount must have at most 2 decimal places.')
        return amount.quantize(Decimal('0.01'))


class OrderListSerializer(OrderProgressMixin, serializers.ModelSerializer):
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    meal_type_display = serializers.SerializerMethodField()
    meal_public_id = serializers.UUIDField(source='meal.public_id', read_only=True)
    expected_deliveries = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    remaining_count = serializers.SerializerMethodField()
    active_days_this_month = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'public_id',
            'meal_public_id',
            'meal_name_snapshot',
            'meal_type_snapshot',
            'meal_type_display',
            'meal_period_snapshot',
            'total_price_snapshot',
            'per_meal_price_snapshot',
            'order_status',
            'order_status_display',
            'order_start_date',
            'order_end_date',
            'service_days_count',
            'order_month',
            'customer_note',
            'expected_deliveries',
            'delivered_count',
            'remaining_count',
            'active_days_this_month',
            'created_at',
            'updated_at',
        )

    def get_meal_type_display(self, obj):
        return dict(MealCategory.MealType.choices).get(obj.meal_type_snapshot, obj.meal_type_snapshot)


class OrderDetailSerializer(OrderListSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    deliveries = OrderDeliverySerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ('customer', 'deliveries')


class OrderCancelSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default='')


class AdminOrderListSerializer(OrderProgressMixin, serializers.ModelSerializer):
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    meal_type_display = serializers.SerializerMethodField()
    meal_public_id = serializers.UUIDField(source='meal.public_id', read_only=True)
    customer_id = serializers.IntegerField(read_only=True)
    customer_email = serializers.EmailField(source='customer.user.email', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    expected_deliveries = serializers.SerializerMethodField()
    delivered_count = serializers.SerializerMethodField()
    remaining_count = serializers.SerializerMethodField()
    active_days_this_month = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'public_id',
            'customer_id',
            'customer_email',
            'customer_phone',
            'meal',
            'meal_public_id',
            'meal_name_snapshot',
            'meal_type_snapshot',
            'meal_type_display',
            'meal_period_snapshot',
            'total_price_snapshot',
            'per_meal_price_snapshot',
            'order_status',
            'order_status_display',
            'order_start_date',
            'order_end_date',
            'service_days_count',
            'order_month',
            'customer_note',
            'expected_deliveries',
            'delivered_count',
            'remaining_count',
            'active_days_this_month',
            'created_at',
            'updated_at',
        )

    def get_meal_type_display(self, obj):
        return dict(MealCategory.MealType.choices).get(obj.meal_type_snapshot, obj.meal_type_snapshot)


class AdminOrderDetailSerializer(AdminOrderListSerializer):
    deliveries = OrderDeliverySerializer(many=True, read_only=True)

    class Meta(AdminOrderListSerializer.Meta):
        fields = AdminOrderListSerializer.Meta.fields + ('deliveries',)


class MarkDeliverySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            OrderDelivery.DeliveryStatus.DELIVERED,
            OrderDelivery.DeliveryStatus.SKIPPED,
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')


class TodayBoardDeliverySerializer(serializers.ModelSerializer):
    order_public_id = serializers.UUIDField(source='order.public_id', read_only=True)
    customer_email = serializers.EmailField(source='order.customer.user.email', read_only=True)
    meal_name_snapshot = serializers.CharField(source='order.meal_name_snapshot', read_only=True)
    meal_type_snapshot = serializers.CharField(source='order.meal_type_snapshot', read_only=True)
    order_status = serializers.CharField(source='order.order_status', read_only=True)

    class Meta:
        model = OrderDelivery
        fields = (
            'public_id',
            'order_public_id',
            'customer_email',
            'meal_name_snapshot',
            'meal_type_snapshot',
            'order_status',
            'service_date',
            'meal_period',
            'status',
            'skip_source',
            'note',
            'marked_at',
            'delivery_label_snapshot',
            'delivery_full_address_snapshot',
            'delivery_area_snapshot',
            'delivery_city_snapshot',
        )
