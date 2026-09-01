from django.contrib import admin

from notifications.models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    PushCampaign,
    PushCampaignRecipient,
    PushLog,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'is_active')
    search_fields = ('event_type',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'is_read', 'created_at')
    search_fields = ('title', 'user__email')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'push_enabled', 'sms_enabled', 'email_enabled')
    search_fields = ('user__email',)


@admin.register(PushLog)
class PushLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'device_token', 'status', 'sent_at')
    search_fields = ('device_token',)


class PushCampaignRecipientInline(admin.TabularInline):
    model = PushCampaignRecipient
    extra = 0
    readonly_fields = (
        'user',
        'device',
        'status',
        'firebase_message_id',
        'error_message',
        'sent_at',
    )
    can_delete = False


@admin.register(PushCampaign)
class PushCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'title',
        'notification_type',
        'target_type',
        'status',
        'total_sent',
        'total_failed',
        'total_skipped',
        'created_by',
        'created_at',
    )
    list_filter = ('status', 'notification_type', 'target_type')
    search_fields = ('title', 'public_id', 'created_by__email')
    readonly_fields = (
        'public_id',
        'title',
        'body',
        'notification_type',
        'data',
        'created_by',
        'ip_address',
        'user_agent',
        'idempotency_key',
        'target_type',
        'target_config',
        'status',
        'total_targets',
        'total_sent',
        'total_failed',
        'total_skipped',
        'error_summary',
        'created_at',
        'updated_at',
    )
    inlines = [PushCampaignRecipientInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PushCampaignRecipient)
class PushCampaignRecipientAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'user', 'status', 'sent_at')
    list_filter = ('status',)
    search_fields = ('user__email', 'campaign__title')
    readonly_fields = (
        'campaign',
        'user',
        'device',
        'status',
        'firebase_message_id',
        'error_message',
        'sent_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
