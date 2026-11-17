from rest_framework import serializers

from orders.models import GuestMealOrder


class AdminGuestMealOrderSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    customer_public_id = serializers.UUIDField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField(allow_null=True)
    service_date = serializers.DateField()
    meal_period = serializers.ChoiceField(choices=GuestMealOrder.MealPeriod.choices)
    quantity = serializers.IntegerField(help_text='Guest food boxes for this order.')
    package_public_id = serializers.UUIDField(allow_null=True)
    package_name = serializers.CharField(allow_blank=True)
    subscription_public_id = serializers.UUIDField()
    delivery_public_id = serializers.UUIDField(allow_null=True)
    zone_public_id = serializers.UUIDField(allow_null=True, required=False)
    zone_name = serializers.CharField(allow_null=True, required=False)
    base_meal_price = serializers.CharField()
    box_price = serializers.CharField()
    unit_price = serializers.CharField()
    total_amount = serializers.CharField()
    status = serializers.ChoiceField(choices=GuestMealOrder.Status.choices)
    wallet_transaction_public_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()


class AdminGuestMealSummarySerializer(serializers.Serializer):
    order_count = serializers.IntegerField(help_text='Number of Guest Meal orders.')
    box_quantity = serializers.IntegerField(help_text='Sum of guest box quantities.')
    revenue = serializers.CharField(
        help_text='Legacy alias of prepaid_order_value (all statuses in filter).',
    )
    prepaid_order_value = serializers.CharField(
        help_text='Sum of total_amount across filtered orders (scheduled + delivered + cancelled).',
        required=False,
    )
    delivered_recognized_revenue = serializers.CharField(
        help_text='Sum of total_amount for delivered orders in the filter (realized guest revenue).',
        required=False,
    )
    realized_guest_profit = serializers.CharField(
        help_text='Sum of guest MealProfitTransaction.profit_amount for orders in the filter.',
        required=False,
    )
    scheduled_box_quantity = serializers.IntegerField(
        help_text='Boxes with status=scheduled.',
    )
    delivered_box_quantity = serializers.IntegerField(
        help_text='Boxes with status=delivered.',
    )
    cancelled_box_quantity = serializers.IntegerField(
        help_text='Boxes with status=cancelled.',
        required=False,
    )


class AdminGuestMealListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = AdminGuestMealOrderSerializer(many=True)
    summary = AdminGuestMealSummarySerializer()
