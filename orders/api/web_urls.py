from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import AdminOrderViewSet, MealOffSettingsView

app_name = 'web_orders'

router = DefaultRouter()
router.register('', AdminOrderViewSet, basename='admin-order')

mark_delivery = AdminOrderViewSet.as_view({'post': 'mark_delivery'})

urlpatterns = [
    path('meal-off-settings/', MealOffSettingsView.as_view(), name='meal-off-settings'),
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/mark$',
        mark_delivery,
        name='admin-order-mark-delivery-noslash',
    ),
]
