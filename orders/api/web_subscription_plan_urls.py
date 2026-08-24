from django.urls import include, path
from rest_framework.routers import DefaultRouter

from orders.api.subscription_views import AdminSubscriptionPlanViewSet

app_name = 'web_subscription_plans'

router = DefaultRouter()
router.register('', AdminSubscriptionPlanViewSet, basename='admin-subscription-plan')

urlpatterns = [
    path('', include(router.urls)),
]
