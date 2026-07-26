from django.contrib import admin
from django.utils import timezone

from notices.models import Notice
from notices.services import compute_lifecycle_status


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = (
        'display_title',
        'severity',
        'is_published',
        'lifecycle_status',
        'publish_at',
        'publish_until',
        'sort_order',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_published', 'severity')
    search_fields = (
        'title_en',
        'title_bn',
        'body_en',
        'body_bn',
        'public_id',
    )
    readonly_fields = ('public_id', 'created_at', 'updated_at', 'lifecycle_status')
    ordering = ('sort_order', '-publish_at', '-created_at')
    fieldsets = (
        (
            'Content',
            {
                'fields': (
                    'title_en',
                    'title_bn',
                    'body_en',
                    'body_bn',
                    'severity',
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
                    'sort_order',
                    'lifecycle_status',
                ),
                'description': (
                    'Expiry does not flip is_published. After publish_until, '
                    'the public feed hides the notice automatically.'
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

    @admin.display(description='Title')
    def display_title(self, obj: Notice) -> str:
        return obj.title_en or obj.title_bn or '(untitled)'

    @admin.display(description='Status')
    def lifecycle_status(self, obj: Notice) -> str:
        if obj.pk is None:
            return '—'
        return compute_lifecycle_status(obj, at=timezone.now())
