from rest_framework import serializers

from orders.models import GuestMealOrder


class GuestMealUsageSerializer(serializers.Serializer):
    calendar_month = serializers.CharField()
    monthly_limit = serializers.IntegerField()
    used_quantity = serializers.IntegerField()
    remaining_quantity = serializers.IntegerField()


class GuestMealRequestSerializer(serializers.Serializer):
    date = serializers.DateField()
    meal_period = serializers.ChoiceField(choices=GuestMealOrder.MealPeriod.choices)
    quantity = serializers.IntegerField(min_value=1)


class GuestMealPreviewResponseSerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    date = serializers.CharField()
    meal_period = serializers.CharField()
    quantity = serializers.IntegerField()
    base_meal_price = serializers.CharField()
    box_price = serializers.CharField()
    unit_price = serializers.CharField()
    total_price = serializers.CharField()
    monthly_limit = serializers.IntegerField()
    monthly_used = serializers.IntegerField()
    monthly_remaining = serializers.IntegerField()
    monthly_remaining_after_order = serializers.IntegerField()
    recharge_balance = serializers.CharField()
    meal_stop_threshold = serializers.CharField()
    recharge_balance_after = serializers.CharField()
    subscription_public_id = serializers.CharField()
    cutoff_passed = serializers.BooleanField()


class GuestMealOrderSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    date = serializers.CharField()
    meal_period = serializers.CharField()
    quantity = serializers.IntegerField()
    base_meal_price = serializers.CharField()
    box_price = serializers.CharField()
    unit_price = serializers.CharField()
    total_price = serializers.CharField()
    status = serializers.CharField()
    subscription_public_id = serializers.CharField()
    delivery_public_id = serializers.CharField(allow_null=True)
    wallet_transaction_public_id = serializers.CharField(allow_null=True)
    created_at = serializers.CharField()
    monthly_limit = serializers.IntegerField(required=False)
    monthly_used = serializers.IntegerField(required=False)
    monthly_remaining = serializers.IntegerField(required=False)
    monthly_remaining_after_order = serializers.IntegerField(required=False)
    idempotent_replay = serializers.BooleanField(required=False)
