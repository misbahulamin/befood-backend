from datetime import date

from rest_framework import serializers

from ..models import CustomerAddress, CustomerProfile
from ..services.customer_address import (
    assign_default_if_first_present,
    ensure_single_default_delivery,
    handle_default_on_delete,
)
from ..services.profile_completion import update_profile_completion
from ..services.profile_picture import (
    clear_profile_picture,
    get_profile_picture_url,
    upload_profile_picture,
    validate_image_extension,
    validate_image_size,
)
from ..validators import validate_bangladesh_phone


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            'public_id',
            'address_type',
            'full_address',
            'city',
            'area',
            'building_name',
            'floor',
            'flat_number',
            'landmark',
            'latitude',
            'longitude',
            'is_default_delivery',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'created_at', 'updated_at')


class CustomerAddressCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            'address_type',
            'full_address',
            'city',
            'area',
            'building_name',
            'floor',
            'flat_number',
            'landmark',
            'latitude',
            'longitude',
            'is_default_delivery',
        )

    def validate_full_address(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Full address is required.')
        return value.strip()

    def validate(self, attrs):
        address_type = attrs.get('address_type', getattr(self.instance, 'address_type', None))
        is_default = attrs.get(
            'is_default_delivery',
            getattr(self.instance, 'is_default_delivery', False),
        )
        if is_default and address_type != CustomerAddress.AddressType.PRESENT:
            raise serializers.ValidationError(
                {'is_default_delivery': 'Only present addresses can be set as default delivery.'}
            )
        return attrs

    def create(self, validated_data):
        customer_profile = self.context['customer_profile']
        is_default = validated_data.pop('is_default_delivery', False)
        address = CustomerAddress.objects.create(
            customer_profile=customer_profile,
            **validated_data,
        )
        if is_default:
            ensure_single_default_delivery(customer_profile, exclude_address_id=address.pk)
            address.is_default_delivery = True
            address.save(update_fields=['is_default_delivery', 'updated_at'])
        else:
            assign_default_if_first_present(customer_profile, address)
        update_profile_completion(customer_profile)
        return address

    def update(self, instance, validated_data):
        customer_profile = instance.customer_profile
        is_default = validated_data.pop('is_default_delivery', instance.is_default_delivery)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if is_default:
            ensure_single_default_delivery(customer_profile, exclude_address_id=instance.pk)
            instance.is_default_delivery = True
        else:
            instance.is_default_delivery = is_default
        instance.save()
        update_profile_completion(customer_profile)
        return instance


class CustomerProfileFieldsSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfile
        fields = (
            'phone',
            'occupation',
            'is_bachelor',
            'is_email_verified',
            'birth_date',
            'gender',
            'height_cm',
            'weight_kg',
            'emergency_contact_name',
            'emergency_contact_phone',
            'organization_name',
            'academic_year_or_position',
            'has_allergy',
            'allergy_details',
            'restricted_foods',
            'preferred_food_type',
            'spice_level',
            'religious',
            'delivery_instruction',
            'preferred_delivery_time',
            'profile_image_url',
            'profile_completed',
            'profile_completion_percentage',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'phone',
            'occupation',
            'is_bachelor',
            'is_email_verified',
            'profile_image_url',
            'profile_completed',
            'profile_completion_percentage',
            'created_at',
            'updated_at',
        )

    def get_profile_image_url(self, profile):
        return get_profile_picture_url(profile, request=self.context.get('request'))


class CustomerProfileImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)

    def validate_image(self, value):
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def create(self, validated_data):
        profile = self.context['customer_profile']
        url = upload_profile_picture(profile, validated_data['image'])
        return {'profile_image_url': url, 'message': 'Profile picture updated.'}


class CustomerExtendedProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)
    occupation = serializers.ChoiceField(
        choices=CustomerProfile.Occupation.choices,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    is_bachelor = serializers.BooleanField(required=False, allow_null=True)
    # Write-only: null clears the picture; non-null strings are ignored (upload via dedicated endpoint).
    profile_image_url = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
    )

    class Meta:
        model = CustomerProfile
        fields = (
            'first_name',
            'last_name',
            'phone',
            'occupation',
            'is_bachelor',
            'birth_date',
            'gender',
            'height_cm',
            'weight_kg',
            'emergency_contact_name',
            'emergency_contact_phone',
            'organization_name',
            'academic_year_or_position',
            'has_allergy',
            'allergy_details',
            'restricted_foods',
            'preferred_food_type',
            'spice_level',
            'religious',
            'delivery_instruction',
            'preferred_delivery_time',
            'profile_image_url',
        )

    def validate_first_name(self, value):
        return value.strip() if value is not None else value

    def validate_last_name(self, value):
        return value.strip() if value is not None else value

    def validate_phone(self, value):
        if value in (None, ''):
            return None
        value = validate_bangladesh_phone(value, 'phone')
        qs = CustomerProfile.objects.filter(phone=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Phone already exists.')
        return value

    def validate_occupation(self, value):
        if value in (None, ''):
            return None
        return value

    def validate_birth_date(self, value):
        if value and value > date.today():
            raise serializers.ValidationError('Birth date cannot be in the future.')
        return value

    def validate_height_cm(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('Height must be a positive value.')
        return value

    def validate_weight_kg(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('Weight must be a positive value.')
        return value

    def validate_emergency_contact_phone(self, value):
        return validate_bangladesh_phone(value, 'emergency_contact_phone')

    def validate(self, attrs):
        has_allergy = attrs.get('has_allergy', getattr(self.instance, 'has_allergy', False))
        allergy_details = attrs.get('allergy_details', getattr(self.instance, 'allergy_details', ''))
        if has_allergy and not (allergy_details and allergy_details.strip()):
            raise serializers.ValidationError(
                {'allergy_details': 'Allergy details are required when has_allergy is true.'}
            )
        return attrs

    def update(self, instance, validated_data):
        from ..services.profile_onboarding import update_customer_onboarding_profile

        clear_picture = False
        if 'profile_image_url' in validated_data:
            value = validated_data.pop('profile_image_url')
            # Only explicit null clears; data/remote URLs are ignored for security.
            if value is None:
                clear_picture = True

        update_customer_onboarding_profile(instance, validated_data)
        if clear_picture:
            clear_profile_picture(instance)
        instance.refresh_from_db()
        update_profile_completion(instance)
        return instance


class CustomerExtendedProfileSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    customer_profile = serializers.SerializerMethodField()
    addresses = CustomerAddressSerializer(many=True, read_only=True)
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    profile_completed = serializers.BooleanField(read_only=True)
    onboarding_completion = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    def get_user(self, profile):
        user = profile.user
        return {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }

    def get_customer_profile(self, profile):
        return CustomerProfileFieldsSerializer(profile, context=self.context).data

    def get_onboarding_completion(self, profile):
        from ..services.profile_onboarding import get_onboarding_completion

        return get_onboarding_completion(profile.user, profile)

    def get_profile_image_url(self, profile):
        return get_profile_picture_url(profile, request=self.context.get('request'))


class CustomerProfileCompletionSerializer(serializers.Serializer):
    profile_completion_percentage = serializers.IntegerField(read_only=True)
    profile_completed = serializers.BooleanField(read_only=True)
