from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationTemplateViewSet, NotificationViewSet, NotificationPreferenceViewSet, PushLogViewSet
router = DefaultRouter()
router.register(r'notificationtemplate', NotificationTemplateViewSet)
router.register(r'notification', NotificationViewSet)
router.register(r'notificationpreference', NotificationPreferenceViewSet)
router.register(r'pushlog', PushLogViewSet)
urlpatterns = [path("", include(router.urls))]