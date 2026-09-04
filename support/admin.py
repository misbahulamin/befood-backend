from django.contrib import admin

from support.models import SupportConversation, SupportMessage


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    can_delete = False
    fields = (
        'public_id',
        'sender_type',
        'sender_user',
        'body',
        'is_read_by_customer',
        'is_read_by_admin',
        'created_at',
    )
    readonly_fields = fields
    ordering = ('created_at',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'customer',
        'status',
        'last_message_at',
        'customer_unread_count',
        'admin_unread_count',
        'updated_at',
    )
    list_filter = ('status',)
    search_fields = (
        'public_id',
        'customer__user__email',
        'customer__user__username',
        'customer__phone',
        'last_message',
    )
    readonly_fields = (
        'public_id',
        'customer',
        'last_message',
        'last_message_at',
        'customer_unread_count',
        'admin_unread_count',
        'created_at',
        'updated_at',
    )
    inlines = [SupportMessageInline]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = (
        'public_id',
        'conversation',
        'sender_type',
        'sender_user',
        'is_read_by_customer',
        'is_read_by_admin',
        'created_at',
    )
    list_filter = ('sender_type', 'is_read_by_customer', 'is_read_by_admin')
    search_fields = ('public_id', 'body', 'conversation__public_id')
    readonly_fields = (
        'public_id',
        'conversation',
        'sender_type',
        'sender_user',
        'body',
        'is_read_by_customer',
        'is_read_by_admin',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
