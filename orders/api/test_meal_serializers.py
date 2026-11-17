from rest_framework import serializers

from orders.models import TestMealOrder


class TestMealDeliveryWindowSerializer(serializers.Serializer):
    start = serializers.CharField(help_text='HH:MM delivery window start.')
    end = serializers.CharField(help_text='HH:MM delivery window end.')


class TestMealDeliveryWindowsSerializer(serializers.Serializer):
    lunch = TestMealDeliveryWindowSerializer()
    dinner = TestMealDeliveryWindowSerializer()


class TestMealEligibilitySerializer(serializers.Serializer):
    """Shape of ``eligibility_for_customer``."""

    eligible = serializers.BooleanField()
    is_active_subscriber = serializers.BooleanField()
    quota_limit = serializers.IntegerField()
    quota_used = serializers.IntegerField()
    quota_remaining = serializers.IntegerField()
    reason = serializers.CharField(allow_null=True)
    message_bn = serializers.CharField(allow_null=True)
    message_en = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    delivery_windows = TestMealDeliveryWindowsSerializer()


class TestMealPackageSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    meal_name = serializers.CharField()


class TestMealQuoteRequestSerializer(serializers.Serializer):
    service_date = serializers.DateField()
    meal_period = serializers.ChoiceField(choices=TestMealOrder.MealPeriod.choices)
    package_public_id = serializers.UUIDField()


class TestMealQuoteResponseSerializer(serializers.Serializer):
    """Shape of ``quote_to_dict``."""

    service_date = serializers.CharField()
    meal_period = serializers.CharField()
    package_public_id = serializers.CharField()
    package_name = serializers.CharField()
    meal_price = serializers.CharField()
    box_charge = serializers.CharField()
    total_price = serializers.CharField()
    currency = serializers.CharField()
    delivery_window_start = serializers.CharField()
    delivery_window_end = serializers.CharField()
    cutoff_passed = serializers.BooleanField()


class TestMealCreateSerializer(serializers.Serializer):
    service_date = serializers.DateField()
    meal_period = serializers.ChoiceField(choices=TestMealOrder.MealPeriod.choices)
    package_public_id = serializers.UUIDField()
    address_public_id = serializers.UUIDField()
    special_instructions = serializers.CharField(
        required=False, allow_blank=True, max_length=2000
    )
    source_channel = serializers.CharField(
        required=False, allow_blank=True, max_length=64
    )


class TestMealOrderAddressSerializer(serializers.Serializer):
    public_id = serializers.CharField(allow_null=True)
    label = serializers.CharField(allow_blank=True)
    full_address = serializers.CharField(allow_blank=True)
    area = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)


class TestMealOrderSerializer(serializers.Serializer):
    """Shape of ``serialize_test_meal_order``."""

    public_id = serializers.UUIDField()
    service_date = serializers.CharField()
    meal_period = serializers.CharField()
    package_public_id = serializers.CharField(allow_null=True)
    package_name = serializers.CharField(allow_blank=True)
    special_instructions = serializers.CharField(allow_blank=True)
    meal_price = serializers.CharField()
    box_charge = serializers.CharField()
    total_price = serializers.CharField()
    currency = serializers.CharField()
    order_status = serializers.CharField()
    payment_status = serializers.CharField()
    payment_method = serializers.CharField()
    delivery_window_start = serializers.CharField()
    delivery_window_end = serializers.CharField()
    address = TestMealOrderAddressSerializer()
    created_at = serializers.CharField(allow_null=True)
    delivered_at = serializers.CharField(allow_null=True)
    cancelled_at = serializers.CharField(allow_null=True)
    idempotent_replay = serializers.BooleanField(required=False)


class TestMealFunnelEventSerializer(serializers.Serializer):
    event_name = serializers.CharField(max_length=64)
    client_event_id = serializers.CharField(max_length=64)
    correlation_id = serializers.CharField(
        required=False, allow_blank=True, max_length=64
    )
    metadata = serializers.JSONField(required=False)
