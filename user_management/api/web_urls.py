from django.urls import include, path
from rest_framework.routers import DefaultRouter

from user_management.api.admin_customer_views import AdminCustomerViewSet

app_name = 'web_customers'

router = DefaultRouter()
router.register(r'', AdminCustomerViewSet, basename='admin-customer')

urlpatterns = [
    path('', include(router.urls)),
]
