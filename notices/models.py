from django.core.exceptions import ValidationError
from django.db import models

from core.models import PublicIdMixin


class Notice(PublicIdMixin, models.Model):
    """Site-wide bilingual notice managed in Django Admin."""

    class Severity(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    title_en = models.CharField(max_length=255, blank=True)
    title_bn = models.CharField(max_length=255, blank=True)
    body_en = models.TextField(blank=True)
    body_bn = models.TextField(blank=True)
    severity = models.CharField(
        max_length=16,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    is_published = models.BooleanField(default=False)
    publish_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Optional start time (UTC). Null = eligible immediately when published.',
    )
    publish_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Optional end time (UTC). Null = no automatic expiry.',
    )
    sort_order = models.IntegerField(
        default=0,
        help_text='Lower values appear first on the public feed.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-publish_at', '-created_at']
        verbose_name = 'notice'
        verbose_name_plural = 'notices'

    def __str__(self):
        return self.title_en or self.title_bn or str(self.public_id)

    def clean(self):
        errors = {}
        if not (self.title_en or '').strip() and not (self.title_bn or '').strip():
            errors['title_en'] = (
                'Provide at least one title (English or Bangla).'
            )
            errors['title_bn'] = (
                'Provide at least one title (English or Bangla).'
            )
        if (
            self.publish_at is not None
            and self.publish_until is not None
            and self.publish_until <= self.publish_at
        ):
            errors['publish_until'] = (
                'publish_until must be after publish_at.'
            )
        if errors:
            raise ValidationError(errors)
