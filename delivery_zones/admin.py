from django.contrib import admin

from delivery_zones.models import DeliveryLocation, DeliverySubLocation, DeliveryZone


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'code',
        'priority',
        'status',
        'assigned_delivery_man',
        'public_id',
        'updated_at',
    )
    list_filter = ('status',)
    search_fields = ('name', 'code', 'public_id')
    raw_id_fields = ('assigned_delivery_man',)
    ordering = ('priority', 'name')


@admin.register(DeliveryLocation)
class DeliveryLocationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'zone',
        'priority',
        'status',
        'public_id',
        'updated_at',
    )
    list_filter = ('status', 'zone')
    search_fields = ('name', 'public_id', 'zone__name', 'zone__code')
    raw_id_fields = ('zone',)
    ordering = ('zone__priority', 'priority', 'name')


@admin.register(DeliverySubLocation)
class DeliverySubLocationAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'location',
        'priority',
        'status',
        'is_default',
        'public_id',
        'updated_at',
    )
    list_filter = ('status', 'is_default', 'location__zone')
    search_fields = (
        'name',
        'public_id',
        'location__name',
        'location__zone__name',
        'location__zone__code',
    )
    raw_id_fields = ('location',)
    ordering = ('location__zone__priority', 'location__priority', 'priority', 'name')
