from django.urls import path
from rest_framework.routers import DefaultRouter

from .delivery_views import (
    CustomerDeliveryPlaceViewSet,
    MealDeliveryDayOverrideView,
    MealDeliveryPreferencePreviewView,
    MealDeliveryPreferenceView,
)
from .deliveryman_views import (
    AdminDeliverymanViewSet,
    DeliverymanCurrentUserView,
    DeliverymanLoginView,
    DeliverymanRegistrationView,
    DeliverymanResendVerificationView,
    DeliverymanVerifyEmailView,
)
from .profile_views import CustomerAddressViewSet, CustomerProfileView, SetDefaultDeliveryAddressView
from .views import (
    AdminCurrentUserView,
    AdminLoginView,
    CustomerLoginView,
    CustomerRegistrationView,
    CurrentUserView,
    LogoutView,
    PasswordResetRequestView,
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
router.register(r'admin/deliverymen', AdminDeliverymanViewSet, basename='admin-deliveryman')

urlpatterns = [
    path('customer/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', CustomerLoginView.as_view(), name='login'),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('me/', CurrentUserView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin/me/', AdminCurrentUserView.as_view(), name='admin-me'),
    path('deliveryman/register/', DeliverymanRegistrationView.as_view(), name='deliveryman-register'),
    path('deliveryman/login/', DeliverymanLoginView.as_view(), name='deliveryman-login'),
    path(
        'deliveryman/verify-email/<uidb64>/<token>/',
        DeliverymanVerifyEmailView.as_view(),
        name='deliveryman-verify-email',
    ),
    path(
        'deliveryman/resend-verification/',
        DeliverymanResendVerificationView.as_view(),
        name='deliveryman-resend-verification',
    ),
    path('deliveryman/me/', DeliverymanCurrentUserView.as_view(), name='deliveryman-me'),
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
