from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.utils import timezone

from .models import (
    AdminProfile,
    AuthSession,
    CustomerAddress,
    CustomerAuthOTP,
    CustomerDeliveryPlace,
    CustomerLocationPreference,
    CustomerLocationSettings,
    CustomerProfile,
    DeviceToken,
    GuestLocationOfferResolution,
    MealDeliveryDayOverride,
    MealDeliveryPreference,
    PendingCustomerRegistration,
    PhoneAuthOTP,
    RiderProfile,
    SocialIdentity,
    StaffProfile,
    UserActivityLog,
)
from .services.deliveryman_auth import approve_deliveryman, reject_deliveryman, set_deliveryman_verified


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    search_fields = ('username', 'email', 'first_name', 'last_name')


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'verified_at', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('verified_at', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if obj.is_verified and obj.verified_at is None:
            obj.verified_at = timezone.now()
        if not obj.is_verified:
            obj.verified_at = None
        super().save_model(request, obj, form, change)
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        obj.user.groups.add(admin_group)
        obj.user.is_active = obj.is_verified
        obj.user.save(update_fields=['is_active'])


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'user',
        'phone',
        'occupation',
        'gender',
        'is_bachelor',
        'is_email_verified',
        'is_phone_verified',
        'meal_service_blocked_low_balance',
        'profile_completion_percentage',
        'profile_completed',
        'created_at',
    )
    search_fields = ('user__email', 'phone', 'user__first_name', 'user__last_name', 'public_id')
    list_filter = (
        'occupation',
        'is_bachelor',
        'is_email_verified',
        'is_phone_verified',
        'gender',
        'profile_completed',
        'meal_service_blocked_low_balance',
    )
    readonly_fields = (
        'public_id',
        'created_at',
        'updated_at',
        'email_verified_at',
        'meal_service_blocked_at',
        'last_low_balance_reminder_on',
    )


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        'customer_profile',
        'address_type',
        'city',
        'area',
        'is_default_delivery',
        'created_at',
    )
    list_filter = ('address_type', 'city', 'is_default_delivery')
    search_fields = (
        'customer_profile__user__email',
        'full_address',
        'area',
        'landmark',
    )


@admin.register(CustomerDeliveryPlace)
class CustomerDeliveryPlaceAdmin(admin.ModelAdmin):
    list_display = (
        'customer_profile',
        'label',
        'city',
        'area',
        'location_source',
        'is_verified_location',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'city', 'location_source', 'is_verified_location')
    search_fields = (
        'customer_profile__user__email',
        'label',
        'full_address',
        'area',
    )


@admin.register(CustomerLocationSettings)
class CustomerLocationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'duplicate_radius_km',
        'max_active_delivery_places',
        'location_refresh_interval_hours',
        'updated_at',
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not CustomerLocationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerLocationPreference)
class CustomerLocationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'customer_profile',
        'active_delivery_place',
        'saved_at',
        'detected_at',
        'is_active',
        'updated_at',
    )
    search_fields = ('customer_profile__user__email',)
    autocomplete_fields = ('customer_profile', 'active_delivery_place')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GuestLocationOfferResolution)
class GuestLocationOfferResolutionAdmin(admin.ModelAdmin):
    list_display = (
        'customer_profile',
        'guest_session_id',
        'status',
        'resolved_at',
        'delivery_place',
        'updated_at',
    )
    list_filter = ('status',)
    search_fields = (
        'customer_profile__user__email',
        'guest_session_id',
    )
    autocomplete_fields = ('customer_profile', 'delivery_place', 'service_area_request')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')


@admin.register(MealDeliveryPreference)
class MealDeliveryPreferenceAdmin(admin.ModelAdmin):
    list_display = ('customer_profile', 'lunch_place', 'dinner_place', 'updated_at')
    search_fields = ('customer_profile__user__email',)
    autocomplete_fields = ('customer_profile', 'lunch_place', 'dinner_place')


@admin.register(MealDeliveryDayOverride)
class MealDeliveryDayOverrideAdmin(admin.ModelAdmin):
    list_display = (
        'customer_profile',
        'meal_period',
        'weekday',
        'place',
        'updated_at',
    )
    list_filter = ('meal_period', 'weekday')
    search_fields = ('customer_profile__user__email', 'place__label')
    autocomplete_fields = ('customer_profile', 'place')


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'phone',
        'is_email_verified',
        'approval_status',
        'is_verified',
        'verified_at',
        'created_at',
    )
    list_filter = ('approval_status', 'is_email_verified', 'is_verified', 'is_available')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'phone', 'address')
    autocomplete_fields = ('user',)
    readonly_fields = (
        'public_id',
        'email_verified_at',
        'verified_at',
        'rejected_at',
        'created_at',
        'updated_at',
    )
    actions = ('approve_selected', 'reject_selected')

    @admin.action(description='Approve selected Delivery Men')
    def approve_selected(self, request, queryset):
        for profile in queryset.select_related('user'):
            if profile.is_email_verified and not profile.is_verified:
                approve_deliveryman(profile, send_email=True)

    @admin.action(description='Reject selected Delivery Men')
    def reject_selected(self, request, queryset):
        for profile in queryset.select_related('user'):
            reject_deliveryman(profile, reason='Rejected from Django admin', send_email=True)

    def save_model(self, request, obj, form, change):
        previous = None
        if change and obj.pk:
            previous = RiderProfile.objects.filter(pk=obj.pk).first()
        super().save_model(request, obj, form, change)
        if previous is None:
            return
        if obj.is_verified and not previous.is_verified:
            set_deliveryman_verified(obj, True, admin_notes=obj.admin_notes, send_email=True)
        elif not obj.is_verified and previous.is_verified:
            set_deliveryman_verified(obj, False, admin_notes=obj.admin_notes, send_email=False)


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'platform',
        'device_name',
        'is_active',
        'last_used_at',
        'created_at',
    )
    list_filter = ('is_active', 'platform')
    search_fields = ('user__email', 'token', 'device_name')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at', 'last_used_at')
    ordering = ('-created_at',)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'outlet_id')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'role')
    autocomplete_fields = ('user',)


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'action', 'ip_address', 'timestamp')
    search_fields = ('user__email', 'action', 'ip_address')
    readonly_fields = ('user', 'action', 'ip_address', 'metadata', 'timestamp')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerAuthOTP)
class CustomerAuthOTPAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'purpose',
        'created_at',
        'expires_at',
        'consumed_at',
        'attempt_count',
        'max_attempts',
    )
    list_filter = ('purpose',)
    search_fields = ('user__email',)
    readonly_fields = (
        'user',
        'purpose',
        'code_hash',
        'created_at',
        'expires_at',
        'consumed_at',
        'attempt_count',
        'max_attempts',
    )
    ordering = ('-created_at',)


@admin.register(PendingCustomerRegistration)
class PendingCustomerRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'email',
        'first_name',
        'last_name',
        'phone',
        'otp_created_at',
        'otp_expires_at',
        'expires_at',
        'created_at',
    )
    search_fields = ('email', 'phone', 'first_name', 'last_name')
    readonly_fields = (
        'email',
        'password_hash',
        'first_name',
        'last_name',
        'phone',
        'occupation',
        'is_bachelor',
        'otp_code_hash',
        'otp_created_at',
        'otp_expires_at',
        'otp_attempt_count',
        'otp_max_attempts',
        'otp_issue_count',
        'otp_window_started_at',
        'created_at',
        'updated_at',
        'expires_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SocialIdentity)
class SocialIdentityAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'provider_user_id', 'email_at_link', 'created_at')
    list_filter = ('provider',)
    search_fields = ('user__email', 'provider_user_id', 'email_at_link')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'platform', 'created_at', 'revoked_at')
    list_filter = ('platform',)
    search_fields = ('user__email', 'key')
    autocomplete_fields = ('user',)
    readonly_fields = ('key', 'created_at', 'last_used_at')


@admin.register(PhoneAuthOTP)
class PhoneAuthOTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'expires_at', 'consumed_at', 'attempt_count', 'created_at')
    search_fields = ('phone',)
    readonly_fields = (
        'phone',
        'code_hash',
        'created_at',
        'expires_at',
        'consumed_at',
        'attempt_count',
        'max_attempts',
        'issue_window_started_at',
        'issues_in_window',
    )

    def has_add_permission(self, request):
        return False
