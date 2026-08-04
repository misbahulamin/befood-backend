from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .cycle_views import (
    IngredientViewSet,
    MealCyclePlanLineViewSet,
    MealCyclePlanViewSet,
    MealCycleViewSet,
)
from .menu_schedule_views import (
    CustomerOrderMenuPreviewView,
    CustomerPackageMenuView,
    CustomerTodayMenuView,
    MenuRevealSettingsView,
    MonthlyMenuScheduleViewSet,
)
from .operational_cost_views import OperationalCostMonthViewSet
from .views import MealCategoryViewSet

app_name = 'meals'

router = DefaultRouter()
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('cycles', MealCycleViewSet, basename='cycles')
router.register('cycle-plans', MealCyclePlanViewSet, basename='cycle-plans')
router.register('cycle-plan-lines', MealCyclePlanLineViewSet, basename='cycle-plan-lines')
router.register(
    'operational-cost-months',
    OperationalCostMonthViewSet,
    basename='operational-cost-months',
)
router.register('menu-schedules', MonthlyMenuScheduleViewSet, basename='menu-schedules')
router.register('', MealCategoryViewSet, basename='meals')

urlpatterns = [
    path('menu-reveal-settings/', MenuRevealSettingsView.as_view(), name='menu-reveal-settings'),
    path('today-menu/', CustomerTodayMenuView.as_view(), name='today-menu'),
    path('my-package-menu/', CustomerPackageMenuView.as_view(), name='my-package-menu'),
    path('order-menu-preview/', CustomerOrderMenuPreviewView.as_view(), name='order-menu-preview'),
    path('', include(router.urls)),
]
