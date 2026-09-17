from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from user_management.models import TimeStampedModel


class DeliveryZone(PublicIdMixin, TimeStampedModel):
    """Operational delivery zone for manual neighborhood grouping (not GPS ServiceArea)."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=64, unique=True)
    priority = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Lower number = higher planning priority.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    assigned_delivery_man = models.ForeignKey(
        'user_management.RiderProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_delivery_zones',
        help_text='Primary Delivery Man for this zone (phase 1: one zone per rider).',
    )
    # Future GPS / map hooks (unused in phase 1).
    centroid_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    centroid_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    boundary_geojson = models.JSONField(null=True, blank=True)
    external_map_place_id = models.CharField(max_length=255, blank=True, default='')
    geo_metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['priority', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['priority'],
                condition=models.Q(status='active'),
                name='uniq_active_delivery_zone_priority',
            ),
            models.UniqueConstraint(
                fields=['assigned_delivery_man'],
                condition=models.Q(assigned_delivery_man__isnull=False),
                name='uniq_delivery_zone_assigned_rider',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'priority']),
        ]

    def __str__(self):
        return f'{self.name} (P{self.priority})'


class DeliveryLocation(PublicIdMixin, TimeStampedModel):
    """Named neighborhood/location inside a DeliveryZone (e.g. Chawkbazar)."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=255)
    zone = models.ForeignKey(
        DeliveryZone,
        on_delete=models.PROTECT,
        related_name='locations',
    )
    priority = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Lower number = closer / deliver first within the zone.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    # Future GPS / map hooks (unused in phase 1).
    centroid_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    centroid_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    boundary_geojson = models.JSONField(null=True, blank=True)
    external_map_place_id = models.CharField(max_length=255, blank=True, default='')
    geo_metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['zone__priority', 'priority', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['zone', 'priority'],
                condition=models.Q(status='active'),
                name='uniq_active_delivery_location_priority_per_zone',
            ),
        ]
        indexes = [
            models.Index(fields=['zone', 'status', 'priority']),
            models.Index(fields=['status', 'name']),
        ]

    def __str__(self):
        return f'{self.name} @ {self.zone.name} (P{self.priority})'
