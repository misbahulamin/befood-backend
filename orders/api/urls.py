from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MealOrderViewSet

app_name = 'orders'

router = DefaultRouter()
router.register('', MealOrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
