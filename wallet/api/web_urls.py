from django.urls import include, path
from rest_framework.routers import DefaultRouter

from wallet.api.web_views import AdminFundingRequestViewSet

app_name = 'web_wallet_funding'

router = DefaultRouter()
router.register('requests', AdminFundingRequestViewSet, basename='funding-request')

urlpatterns = [
    path('', include(router.urls)),
]
