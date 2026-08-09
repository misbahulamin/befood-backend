from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import AdminProfile, CustomerProfile, TimeStampedModel


class ServiceArea(PublicIdMixin, TimeStampedModel):
    """Admin-managed delivery hub: point + radius_km coverage."""

    name = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-90')), MaxValueValidator(Decimal('90'))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-180')), MaxValueValidator(Decimal('180'))],
    )
    radius_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_areas_created',
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self):
        return f'{self.name} ({self.radius_km} km)'


class ServiceAreaRequest(PublicIdMixin, TimeStampedModel):
    """History of customer/guest serviceability checks and demand CTAs."""

    class RequestKind(models.TextChoices):
        CHECK = 'check', 'Check'
        DEMAND = 'demand', 'Demand'

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_area_requests',
    )
    guest_session_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='GPS accuracy in meters when provided by the client.',
    )
    detected_location_name = models.CharField(max_length=255, blank=True, default='')
    formatted_address = models.CharField(max_length=512, blank=True, default='')
    matched_service_area = models.ForeignKey(
        ServiceArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verification_requests',
    )
    distance_km = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    is_serviceable = models.BooleanField(default=False, db_index=True)
    request_kind = models.CharField(
        max_length=20,
        choices=RequestKind.choices,
        default=RequestKind.CHECK,
        db_index=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['is_serviceable', '-requested_at']),
            models.Index(fields=['request_kind', '-requested_at']),
            models.Index(fields=['detected_location_name', '-requested_at']),
        ]

    def __str__(self):
        return f'{self.request_kind} @ {self.latitude},{self.longitude} serviceable={self.is_serviceable}'
