from django.contrib import admin

from delivery_schedules.models import DeliverySchedule


@admin.register(DeliverySchedule)
class DeliveryScheduleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'start_time',
        'end_time',
        'sort_order',
        'is_active',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('sort_order', 'name')
