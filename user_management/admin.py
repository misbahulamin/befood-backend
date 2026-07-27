from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.utils import timezone

from .models import AdminProfile, CustomerAddress, CustomerDeliveryPlace, CustomerProfile, MealDeliveryDayOverride, MealDeliveryPreference


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
        'user',
        'phone',
        'occupation',
        'gender',
        'is_bachelor',
        'is_email_verified',
        'profile_completion_percentage',
        'profile_completed',
        'created_at',
    )
    search_fields = ('user__email', 'phone', 'user__first_name', 'user__last_name')
    list_filter = ('occupation', 'is_bachelor', 'is_email_verified', 'gender', 'profile_completed')


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
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'city')
    search_fields = (
        'customer_profile__user__email',
        'label',
        'full_address',
        'area',
    )


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
