from rest_framework import serializers

from service_area.models import ServiceArea, ServiceAreaRequest


class ServiceAreaCheckSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    accuracy = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    location_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=255,
    )
    formatted_address = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=512,
    )
    guest_session_id = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=64,
    )


class CustomerLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    accuracy = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    location_name = serializers.CharField(allow_null=True, required=False)


class ServiceAreaHubSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    radius_km = serializers.DecimalField(max_digits=8, decimal_places=2)


class ServiceAreaCheckResponseSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    service_available = serializers.BooleanField()
    location_reliable = serializers.BooleanField()
    warning_code = serializers.CharField(allow_null=True, required=False)
    customer_location = CustomerLocationSerializer()
    matched_service_area = ServiceAreaHubSerializer(allow_null=True, required=False)
    nearest_service_area = ServiceAreaHubSerializer(allow_null=True, required=False)
    distance_km = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        allow_null=True,
        required=False,
    )


class ServiceAreaAdminSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ServiceArea
        fields = (
            'public_id',
            'name',
            'latitude',
            'longitude',
            'radius_km',
            'is_active',
            'description',
            'created_by_email',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_created_by_email(self, obj):
        if obj.created_by_id and obj.created_by.user_id:
            return obj.created_by.user.email
        return None


class ServiceAreaAdminWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    radius_km = serializers.DecimalField(max_digits=8, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_active = serializers.BooleanField(required=False, default=True)


class ServiceAreaAdminUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    radius_km = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class ServiceAreaStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class ServiceAreaRequestSerializer(serializers.ModelSerializer):
    matched_service_area_public_id = serializers.UUIDField(
        source='matched_service_area.public_id',
        allow_null=True,
        read_only=True,
    )
    matched_service_area_name = serializers.CharField(
        source='matched_service_area.name',
        allow_null=True,
        read_only=True,
    )
    customer_email = serializers.SerializerMethodField()

    class Meta:
        model = ServiceAreaRequest
        fields = (
            'public_id',
            'request_kind',
            'latitude',
            'longitude',
            'accuracy',
            'detected_location_name',
            'formatted_address',
            'matched_service_area_public_id',
            'matched_service_area_name',
            'distance_km',
            'is_serviceable',
            'guest_session_id',
            'customer_email',
            'requested_at',
            'created_at',
        )
        read_only_fields = fields

    def get_customer_email(self, obj):
        if obj.customer_profile_id and obj.customer_profile.user_id:
            return obj.customer_profile.user.email
        return None


class TopAreaSerializer(serializers.Serializer):
    area_name = serializers.CharField()
    request_count = serializers.IntegerField()


class TopNonServiceableSerializer(serializers.Serializer):
    area_name = serializers.CharField()
    request_count = serializers.IntegerField()
    average_distance_km = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        allow_null=True,
    )


class AnalyticsSummarySerializer(serializers.Serializer):
    top_requested_areas = TopAreaSerializer(many=True)
    top_non_serviceable_areas = TopNonServiceableSerializer(many=True)
