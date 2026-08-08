from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import AdminProfile, CustomerProfile, TimeStampedModel


class AdminWallet(PublicIdMixin, TimeStampedModel):
    """Singleton BeFood platform cash wallet (code=platform)."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        FROZEN = 'frozen', 'Frozen'

    PLATFORM_CODE = 'platform'

    code = models.CharField(max_length=32, unique=True, default=PLATFORM_CODE)
    balance = models.DecimalField(
        max_digits=14,
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
    total_received = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_manual_added = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_withdrawn = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_expenses = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_customer_payments = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_customer_funding = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    total_customer_withdrawals = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        verbose_name = 'Admin wallet'
        verbose_name_plural = 'Admin wallets'

    def __str__(self):
        return f'AdminWallet({self.code}) {self.balance} {self.currency}'


class AdminWalletTransaction(PublicIdMixin, TimeStampedModel):
    class Type(models.TextChoices):
        CUSTOMER_PAYMENT = 'customer_payment', 'Customer payment'
        CUSTOMER_FUNDING = 'customer_funding', 'Customer funding'
        MANUAL_DEPOSIT = 'manual_deposit', 'Manual deposit'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        REFUND_REVERSAL = 'refund_reversal', 'Refund reversal'
        OTHER_INCOME = 'other_income', 'Other income'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        CUSTOMER_WITHDRAW = 'customer_withdraw', 'Customer withdraw'
        CUSTOMER_REFUND = 'customer_refund', 'Customer refund'
        RESTAURANT_SETTLEMENT = 'restaurant_settlement', 'Restaurant settlement'
        RIDER_PAYMENT = 'rider_payment', 'Rider payment'
        OPERATIONAL_EXPENSE = 'operational_expense', 'Operational expense'
        ONAHAR_EXPENSE = 'onahar_expense', 'Onahar expense'
        PROMOTIONAL_COST = 'promotional_cost', 'Promotional cost'
        PLATFORM_EXPENSE = 'platform_expense', 'Platform expense'
        MANUAL_ADJUSTMENT = 'manual_adjustment', 'Manual adjustment'
        INVENTORY_PURCHASE = 'inventory_purchase', 'Inventory purchase'
        INVENTORY_PURCHASE_REVERSAL = (
            'inventory_purchase_reversal',
            'Inventory purchase reversal',
        )

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
        WALLET = 'wallet', 'Customer wallet'
        BKASH = 'bkash', 'bKash'
        NAGAD = 'nagad', 'Nagad'
        OTHER = 'other', 'Other'

    CREDIT_TYPES = {
        Type.CUSTOMER_PAYMENT,
        Type.CUSTOMER_FUNDING,
        Type.MANUAL_DEPOSIT,
        Type.ADJUSTMENT,
        Type.REFUND_REVERSAL,
        Type.OTHER_INCOME,
        Type.INVENTORY_PURCHASE_REVERSAL,
    }
    DEBIT_TYPES = {
        Type.WITHDRAWAL,
        Type.CUSTOMER_WITHDRAW,
        Type.CUSTOMER_REFUND,
        Type.RESTAURANT_SETTLEMENT,
        Type.RIDER_PAYMENT,
        Type.OPERATIONAL_EXPENSE,
        Type.ONAHAR_EXPENSE,
        Type.PROMOTIONAL_COST,
        Type.PLATFORM_EXPENSE,
        Type.MANUAL_ADJUSTMENT,
        Type.INVENTORY_PURCHASE,
    }
    EXPENSE_TYPES = DEBIT_TYPES - {Type.WITHDRAWAL, Type.CUSTOMER_WITHDRAW}

    wallet = models.ForeignKey(
        AdminWallet,
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    type = models.CharField(max_length=40, choices=Type.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    balance_after = models.DecimalField(
        max_digits=14,
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
    source = models.CharField(max_length=64, blank=True, default='')
    reference = models.CharField(max_length=255, blank=True, default='')
    reason = models.CharField(max_length=255, blank=True, default='')
    note = models.CharField(max_length=255, blank=True, default='')
    external_ref = models.CharField(max_length=255, blank=True, default='')
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_transactions',
    )
    order_delivery = models.ForeignKey(
        'orders.OrderDelivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_transactions',
    )
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_transactions',
    )
    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_transactions',
    )
    customer_wallet_transaction = models.ForeignKey(
        'wallet.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_credits',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['wallet', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False),
                name='admin_wallet_txn_unique_idempotency',
            ),
        ]
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['type']),
            models.Index(fields=['direction']),
            models.Index(fields=['method']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.type} {self.direction} {self.amount} ({self.public_id})'


class AdminWalletAuditLog(models.Model):
    class Action(models.TextChoices):
        MANUAL_DEPOSIT = 'manual_deposit', 'Manual deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        EXPENSE = 'expense', 'Expense'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        INVENTORY_PURCHASE = 'inventory_purchase', 'Inventory purchase'
        INVENTORY_PURCHASE_REVERSAL = (
            'inventory_purchase_reversal',
            'Inventory purchase reversal',
        )

    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_wallet_audit_logs',
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    previous_balance = models.DecimalField(max_digits=14, decimal_places=2)
    new_balance = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, default='')
    transaction = models.ForeignKey(
        AdminWalletTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.action} {self.amount} @ {self.created_at}'
