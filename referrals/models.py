from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import CustomerProfile, TimeStampedModel


def seed_commission_percent_from_env() -> Decimal:
    """Bootstrap percent from Django settings / env (used on first singleton create)."""
    raw = getattr(settings, 'REFERRAL_COMMISSION_PERCENT', '5')
    try:
        value = Decimal(str(raw)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('5.00')
    if value < 0 or value > 100:
        return Decimal('5.00')
    return value


class ReferralProgramSettings(models.Model):
    """Singleton: live referral commission percentage for future accruals."""

    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Percent of charged meal amount credited as referral commission (0–100).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Referral program settings'
        verbose_name_plural = 'Referral program settings'

    def __str__(self):
        return f'Referral commission {self.commission_percent}%'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls) -> 'ReferralProgramSettings':
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'commission_percent': seed_commission_percent_from_env()},
        )
        return obj


class ReferralProfile(PublicIdMixin, TimeStampedModel):
    """Permanent referral identity for a customer."""

    customer = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referral_profile',
    )
    code = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r'^BEF[A-Z0-9]{8}$',
                message='Referral code must be BEF followed by 8 alphanumeric characters.',
            )
        ],
    )
    share_count = models.PositiveIntegerField(default=0)
    last_shared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.customer_id})'


class ReferralRelationship(PublicIdMixin, TimeStampedModel):
    """Immutable attribution: one referrer per referred customer."""

    class SourceClient(models.TextChoices):
        MOBILE = 'mobile', 'Mobile'
        WEB = 'web', 'Web'

    referrer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referrals_made',
    )
    referred = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referred_by_relationship',
    )
    referral_code_used = models.CharField(max_length=16)
    source_client = models.CharField(
        max_length=16,
        choices=SourceClient.choices,
        default=SourceClient.MOBILE,
    )
    attributed_at = models.DateTimeField()

    class Meta:
        ordering = ['-attributed_at']
        indexes = [
            models.Index(fields=['referrer']),
            models.Index(fields=['attributed_at']),
            models.Index(fields=['referrer', 'attributed_at']),
        ]

    def __str__(self):
        return f'{self.referrer_id} → {self.referred_id}'


class ReferralCommission(PublicIdMixin, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'
        REVERSED = 'reversed', 'Reversed'

    referrer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referral_commissions_earned',
    )
    referred = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referral_commissions_generated',
        null=True,
        blank=True,
    )
    order_delivery = models.ForeignKey(
        'orders.OrderDelivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_commissions',
    )
    meal_service_date = models.DateField(null=True, blank=True)
    meal_period = models.CharField(max_length=16, blank=True, default='')
    meal_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
    )
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    status_reason = models.CharField(max_length=64, blank=True, default='')
    status_detail = models.CharField(max_length=255, blank=True, default='')
    is_manual = models.BooleanField(default=False)
    reversal_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversals',
    )
    admin_wallet_transaction = models.ForeignKey(
        'admin_wallet.AdminWalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_commissions',
    )
    customer_wallet_transaction = models.ForeignKey(
        'wallet.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_commissions',
    )
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_commission_actions',
    )
    reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order_delivery'],
                condition=(
                    models.Q(order_delivery__isnull=False)
                    & models.Q(is_manual=False)
                    & models.Q(reversal_of__isnull=True)
                ),
                name='referral_commission_unique_delivery',
            ),
        ]
        indexes = [
            models.Index(fields=['referrer', 'created_at']),
            models.Index(fields=['referred']),
            models.Index(fields=['order_delivery']),
            models.Index(fields=['status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.status} {self.commission_amount} ({self.public_id})'


class ReferralValidationEvent(TimeStampedModel):
    """Lightweight event for conversion analytics (validate API)."""

    code = models.CharField(max_length=16, db_index=True)
    is_valid = models.BooleanField(default=False)
    reason = models.CharField(max_length=64, blank=True, default='')
    referrer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referral_validation_events',
    )
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['is_valid', 'created_at']),
        ]
