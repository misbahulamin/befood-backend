from django.urls import path
from rest_framework.routers import DefaultRouter

from .delivery_views import (
    CustomerDeliveryPlaceViewSet,
    MealDeliveryDayOverrideView,
    MealDeliveryPreferencePreviewView,
    MealDeliveryPreferenceView,
)
from .profile_views import CustomerAddressViewSet, CustomerProfileView, SetDefaultDeliveryAddressView
from .views import (
    AdminCurrentUserView,
    AdminLoginView,
    CustomerLoginView,
    CustomerRegistrationView,
    CurrentUserView,
    LogoutView,
    ResendVerificationView,
    VerifyEmailView,
)

app_name = 'user_management'

router = DefaultRouter()
router.register(r'customer/addresses', CustomerAddressViewSet, basename='customer-address')
router.register(
    r'customer/delivery-places',
    CustomerDeliveryPlaceViewSet,
    basename='customer-delivery-place',
)

urlpatterns = [
    path('customer/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', CustomerLoginView.as_view(), name='login'),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('me/', CurrentUserView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin/me/', AdminCurrentUserView.as_view(), name='admin-me'),
    path('customer/profile/', CustomerProfileView.as_view(), name='customer-profile'),
    path(
        'customer/addresses/<uuid:public_id>/set-default/',
        SetDefaultDeliveryAddressView.as_view(),
        name='customer-address-set-default',
    ),
    path(
        'customer/delivery-preferences/',
        MealDeliveryPreferenceView.as_view(),
        name='customer-delivery-preferences',
    ),
    path(
        'customer/delivery-preferences/day-overrides/',
        MealDeliveryDayOverrideView.as_view(),
        name='customer-delivery-day-overrides',
    ),
    path(
        'customer/delivery-preferences/preview/',
        MealDeliveryPreferencePreviewView.as_view(),
        name='customer-delivery-preferences-preview',
    ),
] + router.urls
