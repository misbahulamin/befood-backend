from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActiveNoticeViewSet, NoticeViewSet

app_name = 'notices'

router = DefaultRouter()
# Register public feed first so "active" is not treated as a public_id.
router.register('active', ActiveNoticeViewSet, basename='active')
router.register('', NoticeViewSet, basename='notices')

urlpatterns = [
    path('', include(router.urls)),
]
