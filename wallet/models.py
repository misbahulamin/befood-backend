from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import CustomerProfile, TimeStampedModel


class Wallet(PublicIdMixin, TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        FROZEN = 'frozen', 'Frozen'

    customer = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    currency = models.CharField(max_length=3, default='BDT')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Wallet {self.public_id} ({self.customer})'


class WalletTransaction(PublicIdMixin, TimeStampedModel):
    class Type(models.TextChoices):
        RECHARGE = 'recharge', 'Recharge'
        WITHDRAW = 'withdraw', 'Withdraw'
        PAYMENT = 'payment', 'Payment'
        REFUND = 'refund', 'Refund'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    class Direction(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    class Method(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        BKASH = 'bkash', 'bKash'
        NAGAD = 'nagad', 'Nagad'
        BANK = 'bank', 'Bank'

    PROVIDER_RECHARGE_METHODS = (Method.BKASH, Method.NAGAD, Method.BANK)

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.MANUAL,
    )
    external_ref = models.CharField(max_length=255, blank=True, default='')
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_wallet_transactions',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True, default='')
    invoice_number = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        help_text='Unique receipt identity for completed funding invoices (e.g. recharge).',
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['wallet', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False),
                name='wallet_txn_unique_idempotency_per_wallet',
            ),
            models.UniqueConstraint(
                fields=['method', 'external_ref'],
                condition=(
                    models.Q(type='recharge')
                    & models.Q(method__in=['bkash', 'nagad', 'bank'])
                    & ~models.Q(external_ref='')
                ),
                name='wallet_txn_unique_provider_recharge_ref',
            ),
        ]
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['type']),
            models.Index(fields=['type', 'status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.type} {self.direction} {self.amount} ({self.public_id})'
