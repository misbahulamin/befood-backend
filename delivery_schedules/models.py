from django.core.exceptions import ValidationError
from django.db import models

from core.models import PublicIdMixin


class DeliverySchedule(PublicIdMixin, models.Model):
    """
    Admin-managed informational delivery time window (e.g. Lunch, Dinner).

    Times are Asia/Dhaka wall-clock values for a typical service day.
    This catalog does not drive operational meal_period enums.
    """

    name = models.CharField(max_length=100, unique=True)
    start_time = models.TimeField(
        help_text='Delivery window start (Asia/Dhaka wall-clock).',
    )
    end_time = models.TimeField(
        help_text='Delivery window end (Asia/Dhaka wall-clock). Must be after start_time.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.IntegerField(
        default=0,
        help_text='Lower values appear first on public and admin lists.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name', 'id']
        verbose_name = 'Delivery schedule'
        verbose_name_plural = 'Delivery schedules'
        indexes = [
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        return f'{self.name} ({self.start_time}–{self.end_time})'

    def clean(self):
        errors = {}
        name = (self.name or '').strip()
        if not name:
            errors['name'] = 'Name is required.'
        else:
            self.name = name

        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                errors['end_time'] = (
                    'End time must be after start time (same-day windows only).'
                )

        if errors:
            raise ValidationError(errors)
