from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin


class AssetCategory(PublicIdMixin, models.Model):
    """Classification for permanent (non-consumable) assets."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'asset category'
        verbose_name_plural = 'asset categories'
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        name = (self.name or '').strip()
        if not name:
            errors['name'] = 'Name is required.'
        else:
            self.name = name
        if errors:
            raise ValidationError(errors)


class PermanentAsset(PublicIdMixin, models.Model):
    """
    Durable kitchen/office equipment that is not food inventory.

    Quantity never decreases through cooking or order fulfillment.
    """

    class Status(models.TextChoices):
        IN_SERVICE = 'in_service', 'In service'
        UNDER_MAINTENANCE = 'under_maintenance', 'Under maintenance'
        RETIRED = 'retired', 'Retired'
        DISPOSED = 'disposed', 'Disposed'

    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name='assets',
    )
    asset_tag = models.CharField(
        max_length=64,
        unique=True,
        help_text='Unique label/code for physical identification.',
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.IN_SERVICE,
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Use 1 for a single tagged unit; >1 for homogeneous batches.',
    )
    serial_number = models.CharField(max_length=128, blank=True)
    brand = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=128, blank=True)
    outlet = models.ForeignKey(
        'business.Outlet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permanent_assets',
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default='BDT')
    warranty_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'asset_tag']
        verbose_name = 'permanent asset'
        verbose_name_plural = 'permanent assets'
        indexes = [
            models.Index(fields=['asset_tag']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['status', 'is_active']),
        ]

    def __str__(self):
        return f'{self.asset_tag} — {self.name}'

    def clean(self):
        errors = {}
        name = (self.name or '').strip()
        if not name:
            errors['name'] = 'Name is required.'
        else:
            self.name = name

        tag = (self.asset_tag or '').strip()
        if not tag:
            errors['asset_tag'] = 'Asset tag is required.'
        else:
            self.asset_tag = tag

        if self.quantity is not None and self.quantity < 1:
            errors['quantity'] = 'Quantity must be at least 1.'

        if self.status and self.status not in dict(self.Status.choices):
            errors['status'] = (
                f'Invalid status. Allowed: '
                f'{", ".join(c.value for c in self.Status)}.'
            )

        if (
            self.purchase_date is not None
            and self.warranty_until is not None
            and self.warranty_until < self.purchase_date
        ):
            errors['warranty_until'] = (
                'warranty_until must not be before purchase_date.'
            )

        currency = (self.currency or '').strip().upper()
        if currency:
            if len(currency) != 3:
                errors['currency'] = 'Currency must be a 3-letter ISO code.'
            else:
                self.currency = currency
        else:
            self.currency = 'BDT'

        if errors:
            raise ValidationError(errors)
