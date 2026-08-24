from django.urls import include, path
from rest_framework.routers import DefaultRouter

from orders.api.subscription_views import CustomerSubscriptionPlanViewSet

app_name = 'subscription_plans'

router = DefaultRouter()
router.register('', CustomerSubscriptionPlanViewSet, basename='subscription-plan')

urlpatterns = [
    path('', include(router.urls)),
]
