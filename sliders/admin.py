from django.contrib import admin

from sliders.models import HomeSlider


@admin.register(HomeSlider)
class HomeSliderAdmin(admin.ModelAdmin):
    list_display = (
        'priority',
        'is_active',
        'public_id',
        'created_at',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('public_id',)
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('priority', 'created_at', 'id')
