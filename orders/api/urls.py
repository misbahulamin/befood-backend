from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import MealOffSettingsView, MealOrderViewSet, OrderWalletSettingsView

app_name = 'orders'

router = DefaultRouter()
router.register('', MealOrderViewSet, basename='order')

# Frontend POSTs without trailing slash; APPEND_SLASH cannot redirect POST.
mark_delivery = MealOrderViewSet.as_view({'post': 'mark_delivery'})
meal_off = MealOrderViewSet.as_view({'post': 'meal_off'})
meal_on = MealOrderViewSet.as_view({'post': 'meal_on'})

urlpatterns = [
    path('meal-off-settings/', MealOffSettingsView.as_view(), name='meal-off-settings'),
    path('order-wallet-settings/', OrderWalletSettingsView.as_view(), name='order-wallet-settings'),
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/mark$',
        mark_delivery,
        name='order-mark-delivery-noslash',
    ),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/meal-off$',
        meal_off,
        name='order-meal-off-noslash',
    ),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/meal-on$',
        meal_on,
        name='order-meal-on-noslash',
    ),
]
