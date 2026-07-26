from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActiveAnnouncementViewSet, AnnouncementViewSet

app_name = 'announcements'

router = DefaultRouter()
# Register public feed first so "active" is not treated as a public_id.
router.register('active', ActiveAnnouncementViewSet, basename='active')
router.register('', AnnouncementViewSet, basename='announcements')

urlpatterns = [
    path('', include(router.urls)),
]
