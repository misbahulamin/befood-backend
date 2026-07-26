from django.core.exceptions import ValidationError
from django.db import models

from core.models import PublicIdMixin

from announcements.utils.banner_image import announcement_banner_upload_path


class Announcement(PublicIdMixin, models.Model):
    """Promotional / notice popup managed via verified-admin API."""

    class AnnouncementType(models.TextChoices):
        NOTICE = 'notice', 'Notice'
        OFFER = 'offer', 'Offer'
        NEW_PACKAGE = 'new_package', 'New Package'
        MAINTENANCE = 'maintenance', 'Maintenance'
        ANNOUNCEMENT = 'announcement', 'Announcement'

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        SUCCESS = 'success', 'Success'
        ERROR = 'error', 'Error'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(
        max_length=32,
        choices=AnnouncementType.choices,
        default=AnnouncementType.ANNOUNCEMENT,
    )
    severity = models.CharField(
        max_length=16,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    image = models.ImageField(
        upload_to=announcement_banner_upload_path,
        blank=True,
        null=True,
    )
    button_text = models.CharField(max_length=100, blank=True)
    button_url = models.URLField(blank=True)
    is_published = models.BooleanField(default=False)
    publish_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Optional start time (UTC). Null = eligible immediately when published.',
    )
    publish_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            'Optional end time (UTC), inclusive. Null = no automatic expiry. '
            'Active while publish_until >= now.'
        ),
    )
    priority = models.IntegerField(
        default=0,
        help_text='Higher values appear first on the public feed.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = 'announcement'
        verbose_name_plural = 'announcements'

    def __str__(self):
        return self.title or str(self.public_id)

    def clean(self):
        errors = {}
        if not (self.title or '').strip():
            errors['title'] = 'Title is required.'
        if (
            self.publish_at is not None
            and self.publish_until is not None
            and self.publish_until <= self.publish_at
        ):
            errors['publish_until'] = 'publish_until must be after publish_at.'
        button_text = (self.button_text or '').strip()
        button_url = (self.button_url or '').strip()
        if button_text and not button_url:
            errors['button_url'] = (
                'button_url is required when button_text is provided.'
            )
        if errors:
            raise ValidationError(errors)
