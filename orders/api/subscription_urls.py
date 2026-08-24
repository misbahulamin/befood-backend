from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from orders.api.subscription_views import (
    CustomerSubscriptionPlanViewSet,
    CustomerSubscriptionViewSet,
)

app_name = 'subscriptions'

router = DefaultRouter()
router.register('', CustomerSubscriptionViewSet, basename='subscription')

meal_off = CustomerSubscriptionViewSet.as_view({'post': 'meal_off'})
meal_on = CustomerSubscriptionViewSet.as_view({'post': 'meal_on'})

urlpatterns = [
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/meal-off$',
        meal_off,
        name='subscription-meal-off-noslash',
    ),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/meal-on$',
        meal_on,
        name='subscription-meal-on-noslash',
    ),
]
