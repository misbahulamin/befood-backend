from django.urls import include, path
from rest_framework.routers import DefaultRouter

from support.api.admin_views import AdminSupportConversationViewSet

app_name = 'web_support'

router = DefaultRouter()
router.register('conversations', AdminSupportConversationViewSet, basename='conversation')

urlpatterns = [
    path('', include(router.urls)),
]
