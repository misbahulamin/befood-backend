from django.urls import include, path
from rest_framework.routers import DefaultRouter

from notifications.api.admin_notification_views import (
    AdminPushCampaignSendView,
    AdminPushCampaignViewSet,
)

app_name = 'web_notifications'

router = DefaultRouter()
router.register('', AdminPushCampaignViewSet, basename='admin-push-campaign')

urlpatterns = [
    path('send/', AdminPushCampaignSendView.as_view(), name='admin-push-send'),
    path('', include(router.urls)),
]
