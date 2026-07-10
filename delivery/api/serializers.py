from rest_framework import serializers
from delivery.models import RiderLocation, DeliveryAssignment, DeliveryTracking, DeliveryFeeRule

class RiderLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderLocation
        fields = "__all__"

class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAssignment
        fields = "__all__"

class DeliveryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryTracking
        fields = "__all__"

class DeliveryFeeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryFeeRule
        fields = "__all__"
