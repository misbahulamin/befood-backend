from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationTemplateViewSet,
    NotificationViewSet,
    NotificationPreferenceViewSet,
    PushLogViewSet,
    NotificationInboxListView,
    NotificationUnreadCountView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
)
from .device_token_views import DeviceTokenRegisterView, DeviceTokenRemoveView

app_name = 'notifications'

router = DefaultRouter()
router.register(r'notificationtemplate', NotificationTemplateViewSet)
router.register(r'notification', NotificationViewSet, basename='notification')
router.register(r'notificationpreference', NotificationPreferenceViewSet, basename='notificationpreference')
router.register(r'pushlog', PushLogViewSet, basename='pushlog')
urlpatterns = [
    path('device-token/', DeviceTokenRegisterView.as_view(), name='device-token-register'),
    path('device-token/remove/', DeviceTokenRemoveView.as_view(), name='device-token-remove'),
    path('inbox/', NotificationInboxListView.as_view(), name='inbox-list'),
    path('inbox/unread-count/', NotificationUnreadCountView.as_view(), name='inbox-unread-count'),
    path('inbox/<int:pk>/read/', NotificationMarkReadView.as_view(), name='inbox-mark-read'),
    path('inbox/read-all/', NotificationMarkAllReadView.as_view(), name='inbox-mark-all-read'),
    path('', include(router.urls)),
]
