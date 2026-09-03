from django.contrib import admin

from app_config.models import AppVersionSettings


@admin.register(AppVersionSettings)
class AppVersionSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'latest_version',
        'minimum_supported_version',
        'play_store_url',
        'updated_at',
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not AppVersionSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
