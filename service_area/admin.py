from django.contrib import admin

from service_area.models import ServiceArea, ServiceAreaRequest


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'latitude',
        'longitude',
        'radius_km',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'description', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')


@admin.register(ServiceAreaRequest)
class ServiceAreaRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_kind',
        'latitude',
        'longitude',
        'is_serviceable',
        'detected_location_name',
        'matched_service_area',
        'distance_km',
        'requested_at',
    )
    list_filter = ('request_kind', 'is_serviceable')
    search_fields = (
        'guest_session_id',
        'detected_location_name',
        'public_id',
        'customer_profile__user__email',
    )
    readonly_fields = ('public_id', 'requested_at', 'created_at', 'updated_at')
    raw_id_fields = ('customer_profile', 'matched_service_area')
