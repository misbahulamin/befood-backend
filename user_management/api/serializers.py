from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from ..models import CustomerProfile, DeviceToken, PendingCustomerRegistration
from ..services.identity_normalization import normalize_email, normalize_phone_number, PhoneNormalizationError
from ..services.pending_registration import email_owned_by_verified_customer
from ..validators import format_bd_phone_e164


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = (
            'phone',
            'occupation',
            'is_bachelor',
            'is_email_verified',
            'is_phone_verified',
        )


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    # Optional legacy fields (compatibility window) — not required for signup.
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True, default=None)
    occupation = serializers.ChoiceField(
        choices=CustomerProfile.Occupation.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
        default=None,
    )
    is_bachelor = serializers.BooleanField(required=False, allow_null=True, default=None)

    def validate_phone(self, value):
        if value in (None, ''):
            return None
        try:
            value = normalize_phone_number(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(
                str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)
            ) from exc
        if CustomerProfile.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone already exists.')
        pending_qs = PendingCustomerRegistration.objects.filter(phone=value)
        email = normalize_email(self.initial_data.get('email'))
        if email:
            pending_qs = pending_qs.exclude(email__iexact=email)
        if pending_qs.exists():
            raise serializers.ValidationError('Phone already exists.')
        return value

    def validate_occupation(self, value):
        if value in (None, ''):
            return None
        return value

    def validate_first_name(self, value):
        return value.strip() if value else ''

    def validate_last_name(self, value):
        return value.strip() if value else ''

    def validate_email(self, value):
        value = normalize_email(value)
        if email_owned_by_verified_customer(value):
            raise serializers.ValidationError('Email already exists.')
        # Non-customer accounts (admin/staff) still block the email.
        user = User.objects.filter(email__iexact=value).first()
        if user is not None and not hasattr(user, 'customer_profile'):
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return validated_data


from ..services.admin_access import is_verified_admin


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    device_token = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=255,
        help_text='Optional FCM device token to upsert after successful login.',
    )
    platform = serializers.ChoiceField(
        choices=DeviceToken.Platform.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text='Platform for optional device_token (android/ios/web).',
    )

    def validate_email(self, value):
        return normalize_email(value)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        user = User.objects.filter(email__iexact=email).first()
        profile = getattr(user, 'customer_profile', None) if user else None
        if (
            user is not None
            and profile is not None
            and profile.is_email_verified
            and not user.has_usable_password()
        ):
            # Social/phone account — dedicated code instead of generic invalid credentials.
            attrs['user'] = user
            attrs['password_setup_required'] = True
            attrs['email_not_verified'] = False
            return attrs
        if not user or not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials.')
        if profile is None:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.is_active or not profile.is_email_verified:
            # Correct password but unverified — view triggers verification delivery.
            attrs['user'] = user
            attrs['email_not_verified'] = True
            attrs['password_setup_required'] = False
            return attrs
        device_token = (attrs.get('device_token') or '').strip()
        platform = attrs.get('platform') or ''
        if device_token and not platform:
            raise serializers.ValidationError(
                {'platform': ['Platform is required when device_token is provided.']}
            )
        attrs['user'] = user
        attrs['email_not_verified'] = False
        attrs['password_setup_required'] = False
        attrs['device_token'] = device_token or None
        attrs['platform'] = platform or None
        return attrs


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email').lower()
        password = attrs.get('password')
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials.')
        if user.is_superuser:
            if not user.is_active:
                raise serializers.ValidationError('Account is inactive.')
            attrs['user'] = user
            return attrs
        admin_profile = getattr(user, 'admin_profile', None)
        if admin_profile is None:
            raise serializers.ValidationError('This account is not authorized for admin login.')
        if not admin_profile.is_verified:
            raise serializers.ValidationError('Admin account is not verified yet.')
        if not user.groups.filter(name='ADMIN').exists():
            raise serializers.ValidationError('This account is not authorized for admin login.')
        if not user.is_active:
            raise serializers.ValidationError('Account is inactive.')
        attrs['user'] = user
        return attrs


class AdminCurrentUserSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    admin_profile = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    is_authenticated = serializers.SerializerMethodField()

    def get_user(self, obj):
        return {
            'id': obj.id,
            'email': obj.email,
            'first_name': obj.first_name,
            'last_name': obj.last_name,
            'is_superuser': obj.is_superuser,
        }

    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))

    def get_admin_profile(self, obj):
        admin_profile = getattr(obj, 'admin_profile', None)
        if admin_profile is None:
            return None
        return {
            'is_verified': admin_profile.is_verified,
            'verified_at': admin_profile.verified_at,
        }

    def get_is_admin(self, obj):
        return is_verified_admin(obj)

    def get_is_authenticated(self, obj):
        return obj.is_authenticated


class CurrentUserSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    customer_profile = serializers.SerializerMethodField()
    phone_verification_required = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()
    onboarding_completion = serializers.SerializerMethodField()
    location_confirmation = serializers.SerializerMethodField()
    is_authenticated = serializers.SerializerMethodField()

    def get_user(self, obj):
        user = obj
        return {'id': user.id, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name}

    def get_has_password(self, obj):
        return bool(obj.has_usable_password())

    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))

    def get_customer_profile(self, obj):
        profile = obj.customer_profile
        return {
            'phone': format_bd_phone_e164(profile.phone),
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'is_email_verified': profile.is_email_verified,
            'is_phone_verified': profile.is_phone_verified,
            'gender': profile.gender,
            'profile_completion_percentage': profile.profile_completion_percentage,
            'profile_completed': profile.profile_completed,
        }

    def get_phone_verification_required(self, obj):
        from user_management.services.auth_session import is_phone_verification_required

        return is_phone_verification_required(obj.customer_profile)

    def get_onboarding_completion(self, obj):
        from ..services.profile_onboarding import get_onboarding_completion

        return get_onboarding_completion(obj)

    def get_location_confirmation(self, obj):
        from user_management.services.location_preference import get_location_confirmation_summary

        if not hasattr(obj, 'customer_profile'):
            return {'has_saved_location': False, 'location_confirmed': False}
        return get_location_confirmation_summary(obj.customer_profile)

    def get_is_authenticated(self, obj):
        return obj.is_authenticated


class EmailCheckSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=1)
    password_confirm = serializers.CharField(write_only=True, min_length=1)
    current_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': ['Passwords do not match.']}
            )
        return attrs


class PhoneAvailabilitySerializer(serializers.Serializer):
    phone = serializers.CharField()
    context = serializers.ChoiceField(
        choices=['bind', 'login'],
        required=False,
        allow_blank=True,
        help_text='bind = link phone to logged-in user; login = anonymous phone OTP login.',
    )


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return normalize_email(value)


class PasswordResetValidateSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=1)
    confirm_password = serializers.CharField(write_only=True, min_length=1)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': ['Passwords do not match.']}
            )
        return attrs


class EmailOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return normalize_email(value)

    def validate_otp(self, value):
        value = (value or '').strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError('OTP must be a 6-digit code.')
        return value


class PasswordResetOTPValidateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return normalize_email(value)

    def validate_otp(self, value):
        value = (value or '').strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError('OTP must be a 6-digit code.')
        return value


class PasswordResetOTPConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=1)
    confirm_password = serializers.CharField(write_only=True, min_length=1)

    def validate_email(self, value):
        return normalize_email(value)

    def validate_otp(self, value):
        value = (value or '').strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError('OTP must be a 6-digit code.')
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': ['Passwords do not match.']}
            )
        return attrs


def _optional_device_fields(attrs):
    device_token = (attrs.get('device_token') or '').strip()
    platform = attrs.get('platform') or ''
    if device_token and not platform:
        raise serializers.ValidationError(
            {'platform': ['Platform is required when device_token is provided.']}
        )
    attrs['device_token'] = device_token or None
    attrs['platform'] = platform or None
    return attrs


class PhoneOtpSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        try:
            return normalize_phone_number(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(
                str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)
            ) from exc


class PhoneOtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(min_length=6, max_length=6)
    device_token = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    platform = serializers.ChoiceField(
        choices=DeviceToken.Platform.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_phone(self, value):
        try:
            return normalize_phone_number(value)
        except PhoneNormalizationError as exc:
            raise serializers.ValidationError(
                str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)
            ) from exc

    def validate_otp(self, value):
        value = (value or '').strip()
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError('OTP must be a 6-digit code.')
        return value

    def validate(self, attrs):
        return _optional_device_fields(attrs)


class GoogleOAuthLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    device_token = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    platform = serializers.ChoiceField(
        choices=DeviceToken.Platform.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        return _optional_device_fields(attrs)


class FacebookOAuthLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    device_token = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    platform = serializers.ChoiceField(
        choices=DeviceToken.Platform.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        return _optional_device_fields(attrs)


class LogoutSerializer(serializers.Serializer):
    device_token = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=255,
        help_text='Optional FCM token to deactivate for current-device logout.',
    )