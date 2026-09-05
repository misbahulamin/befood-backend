from django.urls import path
from rest_framework.routers import DefaultRouter

from .delivery_views import (
    CustomerDeliveryPlaceViewSet,
    CustomerLocationGuestOfferDeclineView,
    CustomerLocationGuestOfferView,
    CustomerLocationPreferenceRefreshView,
    CustomerLocationPreferenceSaveAsPlaceView,
    CustomerLocationPreferenceView,
    CustomerLocationSetActivePlaceView,
    CustomerLocationSettingsView,
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
from .profile_views import (
    CustomerAddressViewSet,
    CustomerProfileImageUploadView,
    CustomerProfileView,
    SetDefaultDeliveryAddressView,
)
from .views import (
    AdminCurrentUserView,
    AdminLoginView,
    CustomerEmailCheckView,
    CustomerLoginView,
    CustomerRegistrationView,
    CurrentUserView,
    FacebookOAuthLoginView,
    GoogleOAuthLoginView,
    LogoutAllView,
    LogoutView,
    PasswordResetConfirmOTPView,
    PasswordResetConfirmView,
    PasswordResetRequestOTPView,
    PasswordResetRequestView,
    PasswordResetValidateOTPView,
    PasswordResetValidateView,
    PhoneAvailabilityCheckView,
    PhoneOtpBindSendView,
    PhoneOtpBindVerifyView,
    PhoneOtpSendView,
    PhoneOtpVerifyView,
    ResendVerificationOTPView,
    ResendVerificationView,
    SetPasswordView,
    VerifyEmailOTPView,
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
    path('customer/email-check/', CustomerEmailCheckView.as_view(), name='customer-email-check'),
    path('customer/register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', CustomerLoginView.as_view(), name='login'),
    path('verify-email/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('verify-email/otp/', VerifyEmailOTPView.as_view(), name='verify-email-otp'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend-verification'),
    path(
        'verify-email/resend-otp/',
        ResendVerificationOTPView.as_view(),
        name='verify-email-resend-otp',
    ),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path(
        'password-reset/request-otp/',
        PasswordResetRequestOTPView.as_view(),
        name='password-reset-request-otp',
    ),
    path(
        'password-reset/validate/',
        PasswordResetValidateView.as_view(),
        name='password-reset-validate',
    ),
    path(
        'password-reset/validate-otp/',
        PasswordResetValidateOTPView.as_view(),
        name='password-reset-validate-otp',
    ),
    path(
        'password-reset/confirm/',
        PasswordResetConfirmView.as_view(),
        name='password-reset-confirm',
    ),
    path('password-reset/confirm-otp/', PasswordResetConfirmOTPView.as_view(), name='password-reset-confirm-otp'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    path('me/', CurrentUserView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('logout-all/', LogoutAllView.as_view(), name='logout-all'),
    path('phone/check-availability/', PhoneAvailabilityCheckView.as_view(), name='phone-check-availability'),
    path('phone/otp/send/', PhoneOtpSendView.as_view(), name='phone-otp-send'),
    path('phone/otp/verify/', PhoneOtpVerifyView.as_view(), name='phone-otp-verify'),
    path('phone/otp/bind/send/', PhoneOtpBindSendView.as_view(), name='phone-otp-bind-send'),
    path('phone/otp/bind/verify/', PhoneOtpBindVerifyView.as_view(), name='phone-otp-bind-verify'),
    path('oauth/google/', GoogleOAuthLoginView.as_view(), name='oauth-google'),
    path('oauth/facebook/', FacebookOAuthLoginView.as_view(), name='oauth-facebook'),
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
        'customer/profile/image/',
        CustomerProfileImageUploadView.as_view(),
        name='customer-profile-image',
    ),
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
    path(
        'customer/location-preference/',
        CustomerLocationPreferenceView.as_view(),
        name='customer-location-preference',
    ),
    path(
        'customer/location-preference/refresh/',
        CustomerLocationPreferenceRefreshView.as_view(),
        name='customer-location-preference-refresh',
    ),
    path(
        'customer/location-preference/save-as-place/',
        CustomerLocationPreferenceSaveAsPlaceView.as_view(),
        name='customer-location-preference-save-as-place',
    ),
    path(
        'customer/location-preference/guest-offer/',
        CustomerLocationGuestOfferView.as_view(),
        name='customer-location-guest-offer',
    ),
    path(
        'customer/location-preference/guest-offer/decline/',
        CustomerLocationGuestOfferDeclineView.as_view(),
        name='customer-location-guest-offer-decline',
    ),
    path(
        'customer/location-preference/set-active-place/',
        CustomerLocationSetActivePlaceView.as_view(),
        name='customer-location-set-active-place',
    ),
    path(
        'admin/location-settings/',
        CustomerLocationSettingsView.as_view(),
        name='admin-location-settings',
    ),
] + router.urls
