from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from user_management.models import RiderProfile
from user_management.services.deliveryman_email import PENDING_APPROVAL_MESSAGE


class DeliverymanRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=10)
    address = serializers.CharField()
    password = serializers.CharField(write_only=True)
    vehicle_type = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    license_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')

    def validate_phone(self, value):
        if not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError('Phone must be exactly 10 digits and digits only.')
        if RiderProfile.objects.filter(phone=value).exists():
            raise serializers.ValidationError('Phone already exists.')
        return value

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class DeliverymanLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email').lower()
        password = attrs.get('password')
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError('Invalid credentials.')
        profile = getattr(user, 'rider_profile', None)
        if profile is None:
            raise serializers.ValidationError('This account is not authorized for delivery man login.')
        if not profile.is_email_verified:
            raise serializers.ValidationError('Please verify your email before login.')
        if not profile.is_verified or not user.is_active:
            raise serializers.ValidationError(PENDING_APPROVAL_MESSAGE)
        attrs['user'] = user
        return attrs


class DeliverymanResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class DeliverymanCurrentUserSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    rider_profile = serializers.SerializerMethodField()
    is_authenticated = serializers.SerializerMethodField()

    def get_user(self, obj):
        return {
            'id': obj.id,
            'email': obj.email,
            'first_name': obj.first_name,
            'last_name': obj.last_name,
        }

    def get_groups(self, obj):
        return list(obj.groups.values_list('name', flat=True))

    def get_rider_profile(self, obj):
        profile = obj.rider_profile
        return {
            'public_id': str(profile.public_id),
            'phone': profile.phone,
            'address': profile.address,
            'vehicle_type': profile.vehicle_type,
            'license_number': profile.license_number,
            'is_email_verified': profile.is_email_verified,
            'approval_status': profile.approval_status,
            'is_verified': profile.is_verified,
            'is_available': profile.is_available,
        }

    def get_is_authenticated(self, obj):
        return obj.is_authenticated


class AdminDeliverymanListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = RiderProfile
        fields = (
            'public_id',
            'email',
            'first_name',
            'last_name',
            'phone',
            'address',
            'vehicle_type',
            'license_number',
            'is_email_verified',
            'email_verified_at',
            'approval_status',
            'is_verified',
            'verified_at',
            'rejected_at',
            'rejection_reason',
            'admin_notes',
            'is_available',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class AdminDeliverymanRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class AdminDeliverymanVerifiedStatusSerializer(serializers.Serializer):
    is_verified = serializers.BooleanField()
    admin_notes = serializers.CharField(required=False, allow_blank=True)
