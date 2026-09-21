from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeliveryScheduleAdminViewSet, PublicDeliveryScheduleViewSet

app_name = 'delivery_schedules'

router = DefaultRouter()
# Register named prefixes first so they are never treated as a public_id.
router.register('public', PublicDeliveryScheduleViewSet, basename='public')
router.register('', DeliveryScheduleAdminViewSet, basename='schedules')

urlpatterns = [
    path('', include(router.urls)),
]
