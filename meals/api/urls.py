from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .cycle_views import (
    IngredientViewSet,
    MealCyclePlanLineViewSet,
    MealCyclePlanViewSet,
    MealCycleViewSet,
)
from .views import MealCategoryViewSet

app_name = 'meals'

router = DefaultRouter()
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('cycles', MealCycleViewSet, basename='cycles')
router.register('cycle-plans', MealCyclePlanViewSet, basename='cycle-plans')
router.register('cycle-plan-lines', MealCyclePlanLineViewSet, basename='cycle-plan-lines')
router.register('', MealCategoryViewSet, basename='meals')

urlpatterns = [
    path('', include(router.urls)),
]
