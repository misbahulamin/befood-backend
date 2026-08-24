from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from ..models import CustomerProfile


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = ('phone', 'occupation', 'is_bachelor', 'is_email_verified')


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    # Optional legacy fields (compatibility window) — not required for signup.
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True, default=None)
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
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError('Phone must be exactly 10 digits and digits only.')
        if CustomerProfile.objects.filter(phone=value).exists():
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
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
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

    def validate(self, attrs):
        email = attrs.get('email').lower()
        password = attrs.get('password')
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials.')
        if not user.is_active or not getattr(user, 'customer_profile', None) or not user.customer_profile.is_email_verified:
            raise serializers.ValidationError('Please verify your email before login.')
        attrs['user'] = user
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
    onboarding_completion = serializers.SerializerMethodField()
    is_authenticated = serializers.SerializerMethodField()

    def get_user(self, obj):
        user = obj
        return {'id': user.id, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name}

    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))

    def get_customer_profile(self, obj):
        profile = obj.customer_profile
        return {
            'phone': profile.phone,
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'is_email_verified': profile.is_email_verified,
            'gender': profile.gender,
            'profile_completion_percentage': profile.profile_completion_percentage,
            'profile_completed': profile.profile_completed,
        }

    def get_onboarding_completion(self, obj):
        from ..services.profile_onboarding import get_onboarding_completion

        return get_onboarding_completion(obj)

    def get_is_authenticated(self, obj):
        return obj.is_authenticated


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()
