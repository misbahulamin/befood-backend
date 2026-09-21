from rest_framework import serializers

from delivery_zones.models import DeliveryLocation, DeliveryZone


class DeliveryManSummarySerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    email = serializers.EmailField(allow_null=True, required=False)
    first_name = serializers.CharField(allow_blank=True, required=False)
    last_name = serializers.CharField(allow_blank=True, required=False)


class ZoneSummarySerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField(required=False)
    priority = serializers.IntegerField()
    status = serializers.CharField(required=False)


class LocationSummarySerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    priority = serializers.IntegerField()
    status = serializers.CharField(required=False)


class DeliveryZoneSerializer(serializers.ModelSerializer):
    assigned_delivery_man = serializers.SerializerMethodField()
    location_count = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryZone
        fields = (
            'public_id',
            'name',
            'code',
            'priority',
            'status',
            'assigned_delivery_man',
            'location_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_assigned_delivery_man(self, obj):
        rider = obj.assigned_delivery_man
        if rider is None:
            return None
        return {
            'public_id': str(rider.public_id),
            'email': rider.user.email,
            'first_name': rider.user.first_name,
            'last_name': rider.user.last_name,
        }

    def get_location_count(self, obj):
        annotated = getattr(obj, 'location_count', None)
        if annotated is not None:
            return annotated
        return obj.locations.count()


class DeliveryZoneWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.SlugField(max_length=64)
    priority = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=DeliveryZone.Status.choices,
        required=False,
        default=DeliveryZone.Status.ACTIVE,
    )
    delivery_man_public_id = serializers.UUIDField(required=False, allow_null=True)


class DeliveryZoneUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    code = serializers.SlugField(max_length=64, required=False)
    priority = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=DeliveryZone.Status.choices, required=False)
    delivery_man_public_id = serializers.UUIDField(required=False, allow_null=True)


class DeliveryZoneAssignRiderSerializer(serializers.Serializer):
    delivery_man_public_id = serializers.UUIDField(required=False, allow_null=True)


class DeliveryLocationSerializer(serializers.ModelSerializer):
    zone = serializers.SerializerMethodField()
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryLocation
        fields = (
            'public_id',
            'name',
            'priority',
            'status',
            'zone',
            'centroid_latitude',
            'centroid_longitude',
            'customer_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_zone(self, obj):
        zone = obj.zone
        return {
            'public_id': str(zone.public_id),
            'name': zone.name,
            'code': zone.code,
            'priority': zone.priority,
            'status': zone.status,
        }

    def get_customer_count(self, obj):
        annotated = getattr(obj, 'customer_count', None)
        if annotated is not None:
            return int(annotated)
        return obj.customers.count()


class DeliveryLocationWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    zone_public_id = serializers.UUIDField()
    priority = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=DeliveryLocation.Status.choices,
        required=False,
        default=DeliveryLocation.Status.ACTIVE,
    )
    centroid_latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    centroid_longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )


class DeliveryLocationUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    zone_public_id = serializers.UUIDField(required=False)
    priority = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=DeliveryLocation.Status.choices,
        required=False,
    )
    centroid_latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    centroid_longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )


class DeliveryLocationReorderItemSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    priority = serializers.IntegerField(min_value=1)


class DeliveryLocationReorderSerializer(serializers.Serializer):
    locations = DeliveryLocationReorderItemSerializer(many=True, allow_empty=False)


class CustomerDeliveryLocationAssignSerializer(serializers.Serializer):
    delivery_location_public_id = serializers.UUIDField(required=False, allow_null=True)


class DeliverymanBoardQuerySerializer(serializers.Serializer):
    # service_date / meal_period accepted for backward compatibility but ignored by the view.
    service_date = serializers.DateField(required=False)
    meal_period = serializers.ChoiceField(
        choices=[('lunch', 'Lunch'), ('dinner', 'Dinner')],
        required=False,
    )
    # Exclusive tab filter; takes precedence over include_delivered when set.
    status = serializers.ChoiceField(
        choices=[
            ('scheduled', 'Scheduled / To Deliver'),
            ('delivered', 'Delivered'),
            ('all', 'Scheduled + Delivered'),
        ],
        required=False,
    )
    include_delivered = serializers.BooleanField(required=False, default=False)
    # Foreign zone filters are ignored; board is always scoped to the rider's zone.
    zone_public_id = serializers.UUIDField(required=False)


class DeliverymanMarkDeliverySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[('delivered', 'Delivered')],
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )


class DeliverymanLogisticsTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            ('assigned', 'Assigned'),
            ('accepted', 'Accepted'),
            ('picked_up', 'Picked up'),
            ('out_for_delivery', 'Out for delivery'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
