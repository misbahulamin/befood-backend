from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .admin_guest_meal_views import AdminGuestMealDetailView, AdminGuestMealListView
from .admin_test_meal_views import (
    AdminTestMealAnalyticsView,
    AdminTestMealDetailView,
    AdminTestMealListView,
    AdminTestMealRecordPaymentView,
)
from .views import (
    AdminOrderViewSet,
    KitchenTodayExclusionDetailsView,
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
    path(
        'kitchen/today-exclusion-details/',
        KitchenTodayExclusionDetailsView.as_view(),
        name='kitchen-today-exclusion-details',
    ),
    path('meal-history/', MealDemandHistoryView.as_view(), name='meal-history'),
    path('guest-meals/', AdminGuestMealListView.as_view(), name='admin-guest-meals-list'),
    path(
        'guest-meals/<uuid:public_id>/',
        AdminGuestMealDetailView.as_view(),
        name='admin-guest-meals-detail',
    ),
    path(
        'test-meals/orders/',
        AdminTestMealListView.as_view(),
        name='admin-test-meals-list',
    ),
    path(
        'test-meals/orders/<uuid:public_id>/record-payment/',
        AdminTestMealRecordPaymentView.as_view(),
        name='admin-test-meals-record-payment',
    ),
    path(
        'test-meals/orders/<uuid:public_id>/',
        AdminTestMealDetailView.as_view(),
        name='admin-test-meals-detail',
    ),
    path(
        'test-meals/analytics/',
        AdminTestMealAnalyticsView.as_view(),
        name='admin-test-meals-analytics',
    ),
    path('', include(router.urls)),
    re_path(
        r'^(?P<public_id>[^/.]+)/deliveries/(?P<delivery_id>[^/.]+)/mark$',
        mark_delivery,
        name='admin-order-mark-delivery-noslash',
    ),
]
