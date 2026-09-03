from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminOrderViewSet,
    KitchenTodayMealRequirementView,
    KitchenTodayOrderDetailsView,
    MealDemandHistoryView,
    MealOffSettingsView,
    MealStatisticsView,
    OrderWalletSettingsView,
)

app_name = 'web_orders'

router = DefaultRouter()
router.register('', AdminOrderViewSet, basename='admin-order')

mark_delivery = AdminOrderViewSet.as_view({'post': 'mark_delivery'})

urlpatterns = [
    path('meal-off-settings/', MealOffSettingsView.as_view(), name='meal-off-settings'),
    path('order-wallet-settings/', OrderWalletSettingsView.as_view(), name='order-wallet-settings'),
    path('meal-statistics/', MealStatisticsView.as_view(), name='meal-statistics'),
    path(
        'kitchen/today-meal-requirement/',
        KitchenTodayMealRequirementView.as_view(),
        name='kitchen-today-meal-requirement',
    ),
    path(
        'kitchen/today-order-details/',
        KitchenTodayOrderDetailsView.as_view(),
        name='kitchen-today-order-details',
    ),
    path('meal-history/', MealDemandHistoryView.as_view(), name='meal-history'),
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/mark$',
        mark_delivery,
        name='admin-order-mark-delivery-noslash',
    ),
]
