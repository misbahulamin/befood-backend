from django.urls import include, path
from rest_framework.routers import DefaultRouter

from user_management.api.admin_customer_views import AdminCustomerViewSet
from user_management.api.delivery_views import CustomerLocationSettingsView

app_name = 'web_customers'

router = DefaultRouter()
router.register(r'', AdminCustomerViewSet, basename='admin-customer')

urlpatterns = [
    path(
        'location-settings/',
        CustomerLocationSettingsView.as_view(),
        name='location-settings',
    ),
    path('', include(router.urls)),
]
