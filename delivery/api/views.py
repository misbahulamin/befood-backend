from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from delivery.models import RiderLocation, DeliveryAssignment, DeliveryTracking, DeliveryFeeRule
from .serializers import RiderLocationSerializer, DeliveryAssignmentSerializer, DeliveryTrackingSerializer, DeliveryFeeRuleSerializer

class RiderLocationViewSet(viewsets.ModelViewSet):
    queryset = RiderLocation.objects.all()
    serializer_class = RiderLocationSerializer
    permission_classes = [IsAuthenticated]

class DeliveryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DeliveryAssignment.objects.all()
    serializer_class = DeliveryAssignmentSerializer
    permission_classes = [IsAuthenticated]

class DeliveryTrackingViewSet(viewsets.ModelViewSet):
    queryset = DeliveryTracking.objects.all()
    serializer_class = DeliveryTrackingSerializer
    permission_classes = [IsAuthenticated]

class DeliveryFeeRuleViewSet(viewsets.ModelViewSet):
    queryset = DeliveryFeeRule.objects.all()
    serializer_class = DeliveryFeeRuleSerializer
    permission_classes = [IsAuthenticated]
