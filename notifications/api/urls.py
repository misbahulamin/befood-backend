from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationTemplateViewSet, NotificationViewSet, NotificationPreferenceViewSet, PushLogViewSet
from .device_token_views import DeviceTokenRegisterView, DeviceTokenRemoveView

app_name = 'notifications'

router = DefaultRouter()
router.register(r'notificationtemplate', NotificationTemplateViewSet)
router.register(r'notification', NotificationViewSet)
router.register(r'notificationpreference', NotificationPreferenceViewSet)
router.register(r'pushlog', PushLogViewSet)
urlpatterns = [
    path('device-token/', DeviceTokenRegisterView.as_view(), name='device-token-register'),
    path('device-token/remove/', DeviceTokenRemoveView.as_view(), name='device-token-remove'),
    path('', include(router.urls)),
]