from django.urls import include, path
from rest_framework.routers import DefaultRouter

from user_management.api.admin_deliveryman_360_views import AdminDeliveryman360ViewSet

app_name = 'web_delivery_men'

router = DefaultRouter()
router.register(r'', AdminDeliveryman360ViewSet, basename='admin-delivery-man-360')

urlpatterns = [
    path('', include(router.urls)),
]
