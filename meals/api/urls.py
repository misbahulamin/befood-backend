from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MealCategoryViewSet

app_name = 'meals'

router = DefaultRouter()
router.register('', MealCategoryViewSet, basename='meals_category')

urlpatterns = [
    path('', include(router.urls)),
]
