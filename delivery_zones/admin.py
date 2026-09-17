from django.contrib import admin

from delivery_zones.models import DeliveryLocation, DeliveryZone


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
