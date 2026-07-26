from django.contrib import admin
from django.utils import timezone

from announcements.models import Announcement
from announcements.services import compute_lifecycle_status


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'type',
        'severity',
        'is_published',
        'lifecycle_status',
        'priority',
        'publish_at',
        'publish_until',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_published', 'type', 'severity')
    search_fields = ('title', 'description', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at', 'lifecycle_status')
    ordering = ('-priority', '-created_at')
    fieldsets = (
        (
            'Content',
            {
                'fields': (
                    'title',
                    'description',
                    'type',
                    'severity',
                    'image',
                    'button_text',
                    'button_url',
                ),
            },
        ),
        (
            'Publishing',
            {
                'fields': (
                    'is_published',
                    'publish_at',
                    'publish_until',
                    'priority',
                    'lifecycle_status',
                ),
                'description': (
                    'Expiry does not flip is_published. After publish_until '
                    '(exclusive of times after the inclusive boundary), the '
                    'public feed hides the announcement automatically.'
                ),
            },
        ),
        (
            'Identifiers',
            {
                'fields': ('public_id', 'created_at', 'updated_at'),
            },
        ),
    )

    @admin.display(description='Status')
    def lifecycle_status(self, obj: Announcement) -> str:
        if obj.pk is None:
            return '—'
        return compute_lifecycle_status(obj, at=timezone.now())
