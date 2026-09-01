from rest_framework import serializers

from user_management.models import (
    CustomerDeliveryPlace,
    CustomerLocationSettings,
    MealDeliveryDayOverride,
    MealDeliveryPreference,
)


LOCATION_SOURCE_CHOICES = [
    ('gps', 'GPS'),
    ('manual', 'Manual'),
    ('map_pin', 'Map pin'),
    ('search', 'Search'),
    ('guest_migration', 'Guest migration'),
    ('', 'Legacy / unset'),
]


class CustomerDeliveryPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerDeliveryPlace
        fields = (
            'public_id',
            'label',
            'full_address',
            'city',
            'area',
            'building_name',
            'floor',
            'flat_number',
            'landmark',
            'latitude',
            'longitude',
            'location_source',
            'location_accuracy',
            'formatted_address',
            'is_verified_location',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'created_at', 'updated_at')


class CustomerDeliveryPlaceWriteSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100)
    full_address = serializers.CharField(required=False, allow_blank=True, default='')
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default='Dhaka')
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    building_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    floor = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    flat_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, default=None
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, default=None
    )
    location_source = serializers.ChoiceField(
        choices=LOCATION_SOURCE_CHOICES,
        required=False,
        allow_blank=True,
        default='',
    )
    location_accuracy = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None
    )
    formatted_address = serializers.CharField(
        max_length=512, required=False, allow_blank=True, default=''
    )
    is_verified_location = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)


class MealDeliveryPreferenceSerializer(serializers.ModelSerializer):
    lunch_place_id = serializers.SerializerMethodField()
    dinner_place_id = serializers.SerializerMethodField()
    lunch_place = CustomerDeliveryPlaceSerializer(read_only=True)
    dinner_place = CustomerDeliveryPlaceSerializer(read_only=True)

    class Meta:
        model = MealDeliveryPreference
        fields = (
            'lunch_place_id',
            'dinner_place_id',
            'lunch_place',
            'dinner_place',
            'updated_at',
        )

    def get_lunch_place_id(self, obj):
        return obj.lunch_place.public_id if obj.lunch_place_id else None

    def get_dinner_place_id(self, obj):
        return obj.dinner_place.public_id if obj.dinner_place_id else None


class MealDeliveryPreferenceWriteSerializer(serializers.Serializer):
    lunch_place_id = serializers.UUIDField(required=False, allow_null=True)
    dinner_place_id = serializers.UUIDField(required=False, allow_null=True)


class MealDeliveryDayOverrideSerializer(serializers.ModelSerializer):
    place_id = serializers.UUIDField(source='place.public_id', read_only=True)
    place = CustomerDeliveryPlaceSerializer(read_only=True)

    class Meta:
        model = MealDeliveryDayOverride
        fields = (
            'meal_period',
            'weekday',
            'place_id',
            'place',
            'updated_at',
        )


class MealDeliveryDayOverrideItemSerializer(serializers.Serializer):
    meal_period = serializers.ChoiceField(choices=MealDeliveryDayOverride.MealPeriod.choices)
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    place_id = serializers.UUIDField()


class MealDeliveryDayOverrideReplaceSerializer(serializers.Serializer):
    overrides = MealDeliveryDayOverrideItemSerializer(many=True)


class DeliveryPreviewQuerySerializer(serializers.Serializer):
    """Query params: `from` and `to` (ISO dates)."""

    def to_internal_value(self, data):
        raw_from = data.get('from') if hasattr(data, 'get') else None
        raw_to = data.get('to') if hasattr(data, 'get') else None
        errors = {}
        if not raw_from:
            errors['from'] = ['This query parameter is required.']
        if not raw_to:
            errors['to'] = ['This query parameter is required.']
        if errors:
            raise serializers.ValidationError(errors)

        date_field = serializers.DateField()
        try:
            start = date_field.to_internal_value(raw_from)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'from': exc.detail}) from exc
        try:
            end = date_field.to_internal_value(raw_to)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({'to': exc.detail}) from exc
        return {'from': start, 'to': end}


class DeliveryPreviewItemSerializer(serializers.Serializer):
    service_date = serializers.DateField()
    meal_period = serializers.CharField()
    place_id = serializers.UUIDField(allow_null=True)
    label = serializers.CharField(allow_blank=True)
    full_address = serializers.CharField(allow_blank=True)
    area = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)


class LocationPreferenceRefreshSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    accuracy = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    location_name = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    source = serializers.ChoiceField(
        choices=[c for c in LOCATION_SOURCE_CHOICES if c[0]],
        required=False,
        default='gps',
    )


class LocationPreferenceSaveAsPlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100)
    full_address = serializers.CharField(required=False, allow_blank=True, default='')
    formatted_address = serializers.CharField(
        max_length=512, required=False, allow_blank=True, default=''
    )
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    location_source = serializers.ChoiceField(
        choices=[c for c in LOCATION_SOURCE_CHOICES if c[0]],
        required=False,
        default='gps',
    )
    location_accuracy = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default='Dhaka')
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    building_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    floor = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    flat_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    set_as_active = serializers.BooleanField(required=False, default=True)
    set_as_default_delivery_place = serializers.BooleanField(required=False, default=False)
    set_lunch_default = serializers.BooleanField(required=False, default=False)
    set_dinner_default = serializers.BooleanField(required=False, default=False)


class GuestLocationOfferQuerySerializer(serializers.Serializer):
    guest_session_id = serializers.CharField(max_length=64)


class GuestLocationAcceptSerializer(serializers.Serializer):
    guest_session_id = serializers.CharField(max_length=64)
    label = serializers.CharField(max_length=100)
    full_address = serializers.CharField(required=False, allow_blank=True, default='')
    formatted_address = serializers.CharField(
        max_length=512, required=False, allow_blank=True, default=''
    )
    set_as_default_delivery_place = serializers.BooleanField(required=False, default=False)
    set_lunch_default = serializers.BooleanField(required=False, default=False)
    set_dinner_default = serializers.BooleanField(required=False, default=False)


class SetActivePlaceSerializer(serializers.Serializer):
    place_id = serializers.UUIDField()


class CustomerLocationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerLocationSettings
        fields = (
            'duplicate_radius_km',
            'max_active_delivery_places',
            'location_refresh_interval_hours',
            'updated_at',
        )
        read_only_fields = ('updated_at',)
