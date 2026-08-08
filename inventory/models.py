from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import AdminProfile, TimeStampedModel


def inventory_invoice_upload_path(instance, filename):
    return f'inventory/invoices/{instance.public_id}/{filename}'


class InventoryUnit(models.TextChoices):
    KG = 'kg', 'KG'
    G = 'g', 'Gram'
    L = 'l', 'Liter'
    ML = 'ml', 'Milliliter'
    PIECE = 'piece', 'Piece'
    PACKET = 'packet', 'Packet'
    BOX = 'box', 'Box'
    BOTTLE = 'bottle', 'Bottle'
    BAG = 'bag', 'Bag'


class InventoryItem(PublicIdMixin, TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=255)
    name_normalized = models.CharField(max_length=255, unique=True, db_index=True)
    default_unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    category = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    minimum_stock_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    quantity_on_hand = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
    )
    average_unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    linked_ingredient = models.ForeignKey(
        'meals.Ingredient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items',
    )
    created_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_items_created',
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['-updated_at']),
        ]

    def __str__(self):
        return f'{self.name} ({self.quantity_on_hand} {self.default_unit})'

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity_on_hand <= 0

    @property
    def is_low_stock(self) -> bool:
        if self.minimum_stock_level is None:
            return False
        return (
            self.quantity_on_hand > 0
            and self.quantity_on_hand <= self.minimum_stock_level
        )

    @property
    def stock_value(self) -> Decimal:
        if self.quantity_on_hand <= 0 or self.average_unit_cost is None:
            return Decimal('0.00')
        return (self.quantity_on_hand * self.average_unit_cost).quantize(
            Decimal('0.01')
        )


class InventoryPurchase(PublicIdMixin, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    purchase_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    invoice = models.FileField(
        upload_to=inventory_invoice_upload_path,
        null=True,
        blank=True,
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    currency = models.CharField(max_length=3, default='BDT')
    created_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_purchases_created',
    )
    confirmed_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_purchases_confirmed',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_purchases_cancelled',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    wallet_transaction = models.ForeignKey(
        'admin_wallet.AdminWalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_purchases',
    )
    reversal_wallet_transaction = models.ForeignKey(
        'admin_wallet.AdminWalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_purchase_reversals',
    )

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['supplier']),
            models.Index(fields=['-purchase_date']),
        ]

    def __str__(self):
        return f'Purchase {self.public_id} ({self.status})'


class InventoryPurchaseLine(models.Model):
    purchase = models.ForeignKey(
        InventoryPurchase,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='purchase_lines',
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    quantity_base = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Quantity converted to the item default unit.',
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Cost per item default unit.',
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.item_id}: {self.quantity} {self.unit}'


class InventoryKitchenUsage(PublicIdMixin, TimeStampedModel):
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='kitchen_usages',
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    quantity_base = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    purpose = models.CharField(max_length=255, blank=True, default='')
    menu_reference = models.CharField(max_length=255, blank=True, default='')
    kitchen_batch = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    issued_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_kitchen_usages',
    )
    quantity_after = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['item', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'Usage {self.item_id} -{self.quantity_base}'


class InventoryWastage(PublicIdMixin, TimeStampedModel):
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='wastages',
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    quantity_base = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True, default='')
    recorded_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_wastages',
    )
    quantity_after = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Wastage {self.item_id} -{self.quantity_base}'


class InventoryAdjustment(PublicIdMixin, TimeStampedModel):
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='adjustments',
    )
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    quantity_delta_base = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=255)
    note = models.TextField(blank=True, default='')
    adjusted_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_adjustments',
    )
    quantity_after = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Adjustment {self.item_id} {self.quantity_delta_base}'


class InventoryStockMovement(PublicIdMixin, TimeStampedModel):
    class Type(models.TextChoices):
        PURCHASE = 'purchase', 'Purchase'
        KITCHEN_USAGE = 'kitchen_usage', 'Kitchen usage'
        WASTAGE = 'wastage', 'Wastage'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        PURCHASE_REVERSAL = 'purchase_reversal', 'Purchase reversal'

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name='movements',
    )
    type = models.CharField(max_length=40, choices=Type.choices)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    quantity_before = models.DecimalField(max_digits=14, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_stock_movements',
    )
    note = models.CharField(max_length=255, blank=True, default='')
    purchase = models.ForeignKey(
        InventoryPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )
    purchase_line = models.ForeignKey(
        InventoryPurchaseLine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )
    kitchen_usage = models.ForeignKey(
        InventoryKitchenUsage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )
    wastage = models.ForeignKey(
        InventoryWastage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )
    adjustment = models.ForeignKey(
        InventoryAdjustment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movements',
    )
    unit_cost_at_movement = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['item', '-created_at']),
            models.Index(fields=['type', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.type} {self.quantity_delta} {self.item_id}'


class InventoryAuditLog(models.Model):
    class Action(models.TextChoices):
        ITEM_CREATED = 'item_created', 'Item created'
        ITEM_UPDATED = 'item_updated', 'Item updated'
        PURCHASE_ADDED = 'purchase_added', 'Purchase added'
        PURCHASE_CONFIRMED = 'purchase_confirmed', 'Purchase confirmed'
        PURCHASE_CANCELLED = 'purchase_cancelled', 'Purchase cancelled'
        STOCK_USED = 'stock_used', 'Stock used'
        STOCK_ADJUSTED = 'stock_adjusted', 'Stock adjusted'
        WASTAGE_ADDED = 'wastage_added', 'Wastage added'
        INVOICE_UPLOADED = 'invoice_uploaded', 'Invoice uploaded'
        WALLET_DEDUCTED = 'wallet_deducted', 'Wallet deducted'
        WALLET_REVERSED = 'wallet_reversed', 'Wallet reversed'

    actor_admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_audit_logs',
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    purchase = models.ForeignKey(
        InventoryPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    previous_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    reference_id = models.CharField(max_length=64, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.action} @ {self.created_at}'
