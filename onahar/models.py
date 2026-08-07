from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import CustomerProfile, TimeStampedModel


class OnaharSettings(TimeStampedModel):
    """Singleton-style global Onahar configuration (use pk=1)."""

    contribution_target = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
        help_text='Eligible meals required for one Onahar meal contribution.',
    )
    total_contributed_meals = models.PositiveIntegerField(default=0)
    total_distributed_meals = models.PositiveIntegerField(default=0)
    available_meals = models.IntegerField(
        default=0,
        help_text='Denormalized: contributed − distributed (may go negative only via adjustments).',
    )

    class Meta:
        verbose_name = 'Onahar settings'
        verbose_name_plural = 'Onahar settings'

    def __str__(self):
        return f'OnaharSettings(target={self.contribution_target})'


class OnaharTargetHistory(models.Model):
    previous_target = models.PositiveIntegerField()
    new_target = models.PositiveIntegerField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_target_changes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.previous_target} → {self.new_target}'


class OnaharMonthlyProgress(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='onahar_monthly_progress',
    )
    year_month = models.CharField(max_length=7, help_text='YYYY-MM in project timezone')
    target_snapshot = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    net_points = models.IntegerField(default=0)
    contributions_earned = models.PositiveIntegerField(default=0)
    expired_points = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-year_month', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'year_month'],
                name='onahar_unique_customer_month_progress',
            ),
        ]
        indexes = [
            models.Index(fields=['year_month', 'status']),
            models.Index(fields=['customer', '-year_month']),
        ]

    def __str__(self):
        return f'{self.customer_id} {self.year_month} ({self.net_points}/{self.target_snapshot})'

    @property
    def remaining_points(self):
        if self.target_snapshot <= 0:
            return 0
        return self.net_points % self.target_snapshot

    @property
    def points_to_next_contribution(self):
        rem = self.remaining_points
        if rem == 0 and self.net_points > 0:
            return self.target_snapshot
        if rem == 0:
            return self.target_snapshot
        return self.target_snapshot - rem


class OnaharPointEvent(models.Model):
    class EventType(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        REVERSE = 'reverse', 'Reverse'

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='onahar_point_events',
    )
    order_delivery = models.ForeignKey(
        'orders.OrderDelivery',
        on_delete=models.PROTECT,
        related_name='onahar_point_events',
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    year_month = models.CharField(max_length=7)
    points_delta = models.SmallIntegerField(
        help_text='+1 for credit, -1 for reverse',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order_delivery', 'event_type'],
                name='onahar_unique_delivery_point_event_type',
            ),
        ]
        indexes = [
            models.Index(fields=['customer', 'year_month']),
            models.Index(fields=['order_delivery']),
        ]

    def __str__(self):
        return f'{self.event_type} {self.points_delta} delivery={self.order_delivery_id}'


class OnaharContribution(PublicIdMixin, TimeStampedModel):
    class Kind(models.TextChoices):
        EARNED = 'earned', 'Earned'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='onahar_contributions',
    )
    year_month = models.CharField(max_length=7)
    meals = models.IntegerField(
        help_text='+1 earned contribution or -1 compensating adjustment',
    )
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.EARNED,
    )
    monthly_progress = models.ForeignKey(
        OnaharMonthlyProgress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contributions',
    )
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['year_month']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.kind} {self.meals} meal(s) ({self.public_id})'


class OnaharDistribution(PublicIdMixin, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    full_address = models.TextField(blank=True, default='')
    distribution_date = models.DateField()
    meals_distributed = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    description = models.TextField(blank=True, default='')
    beneficiary_info = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_distributions_created',
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_distributions_published',
    )
    published_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_distributions_cancelled',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-distribution_date', '-created_at']
        indexes = [
            models.Index(fields=['status', '-distribution_date']),
        ]

    def __str__(self):
        return f'{self.title} ({self.status})'


class OnaharDistributionMedia(PublicIdMixin, TimeStampedModel):
    distribution = models.ForeignKey(
        OnaharDistribution,
        on_delete=models.CASCADE,
        related_name='media',
    )
    image = models.ImageField(upload_to='onahar/distributions/%Y/%m/')
    caption = models.CharField(max_length=255, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_distribution_media',
    )

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'Media for {self.distribution_id}'


class OnaharFundLedgerEntry(PublicIdMixin, models.Model):
    class Direction(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'

    class EntryType(models.TextChoices):
        CONTRIBUTION = 'contribution', 'Contribution'
        CONTRIBUTION_ADJUSTMENT = 'contribution_adjustment', 'Contribution adjustment'
        DISTRIBUTION = 'distribution', 'Distribution'
        DISTRIBUTION_RESTORE = 'distribution_restore', 'Distribution restore'

    direction = models.CharField(max_length=10, choices=Direction.choices)
    meals = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    entry_type = models.CharField(max_length=40, choices=EntryType.choices)
    balance_after = models.IntegerField()
    contribution = models.ForeignKey(
        OnaharContribution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_ledger_entries',
    )
    distribution = models.ForeignKey(
        OnaharDistribution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fund_ledger_entries',
    )
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['entry_type', '-created_at']),
            models.Index(fields=['direction', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.direction == self.Direction.CREDIT else '-'
        return f'{sign}{self.meals} {self.entry_type}'


class OnaharPrivacyPreference(TimeStampedModel):
    class DisplayMode(models.TextChoices):
        PUBLIC = 'public', 'Public'
        PARTIAL = 'partial', 'Partial'
        ANONYMOUS = 'anonymous', 'Anonymous'

    customer = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='onahar_privacy',
    )
    display_mode = models.CharField(
        max_length=20,
        choices=DisplayMode.choices,
        default=DisplayMode.PARTIAL,
    )

    def __str__(self):
        return f'{self.customer_id}: {self.display_mode}'


class OnaharAuditLog(models.Model):
    action = models.CharField(max_length=64)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='onahar_audit_logs',
    )
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.action} @ {self.created_at}'
