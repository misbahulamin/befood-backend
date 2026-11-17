from rest_framework import serializers

from orders.models import TestMealOrder


class AdminTestMealCustomerSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)


class AdminTestMealAddressSerializer(serializers.Serializer):
    label = serializers.CharField(allow_blank=True)
    full_address = serializers.CharField(allow_blank=True)
    area = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)


class AdminTestMealZoneSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField(allow_blank=True)


class AdminTestMealOrderSerializer(serializers.Serializer):
    """Shape of ``serialize_admin_test_meal_order``."""

    public_id = serializers.UUIDField()
    customer = AdminTestMealCustomerSerializer()
    package_public_id = serializers.CharField(allow_null=True)
    package_name = serializers.CharField(allow_blank=True)
    service_date = serializers.CharField()
    meal_period = serializers.ChoiceField(choices=TestMealOrder.MealPeriod.choices)
    delivery_window_start = serializers.CharField()
    delivery_window_end = serializers.CharField()
    address = AdminTestMealAddressSerializer()
    zone = AdminTestMealZoneSerializer(allow_null=True)
    meal_price = serializers.CharField()
    box_charge = serializers.CharField()
    total_price = serializers.CharField()
    currency = serializers.CharField()
    order_status = serializers.ChoiceField(choices=TestMealOrder.OrderStatus.choices)
    payment_status = serializers.ChoiceField(choices=TestMealOrder.PaymentStatus.choices)
    payment_method = serializers.CharField()
    amount_collected = serializers.CharField(allow_null=True)
    paid_at = serializers.CharField(allow_null=True)
    payment_notes = serializers.CharField(allow_blank=True)
    special_instructions = serializers.CharField(allow_blank=True)
    created_at = serializers.CharField(allow_null=True)
    delivered_at = serializers.CharField(allow_null=True)
    cancelled_at = serializers.CharField(allow_null=True)
    is_currently_active_subscriber = serializers.BooleanField()
    has_subscribed_after_test = serializers.BooleanField()


class AdminTestMealPeriodDistributionSerializer(serializers.Serializer):
    lunch = serializers.IntegerField()
    dinner = serializers.IntegerField()


class AdminTestMealPackagePopularitySerializer(serializers.Serializer):
    package_public_id = serializers.CharField()
    package_name = serializers.CharField(allow_blank=True)
    order_count = serializers.IntegerField()


class AdminTestMealDailySeriesSerializer(serializers.Serializer):
    date = serializers.CharField()
    orders = serializers.IntegerField()
    confirmed_value = serializers.CharField()
    deliveries = serializers.IntegerField()
    conversions = serializers.IntegerField()


class AdminTestMealAnalyticsSerializer(serializers.Serializer):
    """Shape of ``build_test_meal_analytics``."""

    order_count = serializers.IntegerField()
    customer_count = serializers.IntegerField()
    quota_limit_default = serializers.IntegerField()
    confirmed_order_value = serializers.CharField()
    collected_revenue = serializers.CharField()
    outstanding_amount = serializers.CharField()
    unpaid_order_count = serializers.IntegerField()
    paid_order_count = serializers.IntegerField()
    delivered_unpaid_order_count = serializers.IntegerField()
    delivered_customer_count = serializers.IntegerField()
    after_delivery_converted_customer_count = serializers.IntegerField()
    pre_delivery_subscribed_customer_count = serializers.IntegerField()
    primary_conversion_rate = serializers.FloatField()
    period_distribution = AdminTestMealPeriodDistributionSerializer()
    package_popularity = AdminTestMealPackagePopularitySerializer(many=True)
    daily_series = AdminTestMealDailySeriesSerializer(many=True)
    funnel_event_count = serializers.IntegerField()
    revenue_notes = serializers.DictField()


class AdminTestMealRecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    collected_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    payment_status = serializers.ChoiceField(
        choices=TestMealOrder.PaymentStatus.choices,
        required=False,
        help_text='When provided, applies a payment correction instead of a record.',
    )
