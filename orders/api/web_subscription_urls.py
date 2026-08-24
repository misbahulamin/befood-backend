from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from orders.api.subscription_views import AdminSubscriptionPlanViewSet, AdminSubscriptionViewSet

app_name = 'web_subscriptions'

router = DefaultRouter()
router.register('', AdminSubscriptionViewSet, basename='admin-subscription')

mark_delivery = AdminSubscriptionViewSet.as_view({'post': 'mark_delivery'})

urlpatterns = [
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/mark$',
        mark_delivery,
        name='admin-subscription-mark-delivery-noslash',
    ),
]
