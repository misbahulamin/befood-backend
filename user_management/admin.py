from django.contrib import admin

from .models import CustomerAddress, CustomerProfile


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
