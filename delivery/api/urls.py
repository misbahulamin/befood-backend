from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RiderLocationViewSet, DeliveryAssignmentViewSet, DeliveryTrackingViewSet, DeliveryFeeRuleViewSet
router = DefaultRouter()
router.register(r'riderlocation', RiderLocationViewSet)
router.register(r'deliveryassignment', DeliveryAssignmentViewSet)
router.register(r'deliverytracking', DeliveryTrackingViewSet)
router.register(r'deliveryfeerule', DeliveryFeeRuleViewSet)
urlpatterns = [path("", include(router.urls))]