from django.db import transaction
from django.db.models import Count, Q

from delivery_zones.models import DeliveryLocation, DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.priority import (
    allocate_location_priority,
    ensure_active_location_priority_available,
    set_location_priority,
)


def get_location_by_public_id(public_id) -> DeliveryLocation:
    try:
        return (
            DeliveryLocation.objects.select_related(
                'zone',
                'zone__assigned_delivery_man',
                'zone__assigned_delivery_man__user',
            )
            .annotate(customer_count=Count('customers', distinct=True))
            .get(public_id=public_id)
        )
    except DeliveryLocation.DoesNotExist as exc:
        raise DeliveryZoneError('Delivery location not found.', code='LOCATION_NOT_FOUND') from exc


def list_locations(*, zone_public_id=None, status: str | None = None, q: str | None = None):
    qs = (
        DeliveryLocation.objects.select_related(
            'zone',
            'zone__assigned_delivery_man',
            'zone__assigned_delivery_man__user',
        )
        .annotate(customer_count=Count('customers', distinct=True))
        .order_by('zone__priority', 'priority', 'name', 'id')
    )
    if zone_public_id:
        qs = qs.filter(zone__public_id=zone_public_id)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(zone__name__icontains=q))
    return qs


def _normalize_name(name: str) -> str:
    value = (name or '').strip()
    if not value:
        raise DeliveryZoneError('name is required.', code='NAME_REQUIRED')
    return value


def _require_active_zone(zone: DeliveryZone) -> None:
    if zone.status != DeliveryZone.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot use an inactive zone for location assignment.',
            code='ZONE_INACTIVE',
        )


@transaction.atomic
def create_location(
    *,
    name: str,
    zone_public_id,
    priority: int | None = None,
    status: str = DeliveryLocation.Status.ACTIVE,
) -> DeliveryLocation:
    name = _normalize_name(name)
    try:
        zone = DeliveryZone.objects.select_for_update().get(public_id=zone_public_id)
    except DeliveryZone.DoesNotExist as exc:
        raise DeliveryZoneError('Delivery zone not found.', code='ZONE_NOT_FOUND') from exc
    _require_active_zone(zone)

    status_value = status or DeliveryLocation.Status.ACTIVE
    if status_value not in DeliveryLocation.Status.values:
        raise DeliveryZoneError('Invalid location status.', code='INVALID_STATUS')

    if priority is None:
        priority = allocate_location_priority(zone)
    else:
        priority = int(priority)
        if priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if status_value == DeliveryLocation.Status.ACTIVE:
            ensure_active_location_priority_available(zone, priority)

    return DeliveryLocation.objects.create(
        name=name,
        zone=zone,
        priority=priority,
        status=status_value,
    )


@transaction.atomic
def update_location(location: DeliveryLocation, **fields) -> DeliveryLocation:
    location = DeliveryLocation.objects.select_for_update().select_related('zone').get(
        pk=location.pk
    )

    if 'name' in fields and fields['name'] is not None:
        location.name = _normalize_name(fields['name'])

    if 'status' in fields and fields['status'] is not None:
        status_value = fields['status']
        if status_value not in DeliveryLocation.Status.values:
            raise DeliveryZoneError('Invalid location status.', code='INVALID_STATUS')
        location.status = status_value

    target_zone = location.zone
    if 'zone_public_id' in fields and fields['zone_public_id'] is not None:
        try:
            target_zone = DeliveryZone.objects.select_for_update().get(
                public_id=fields['zone_public_id']
            )
        except DeliveryZone.DoesNotExist as exc:
            raise DeliveryZoneError('Delivery zone not found.', code='ZONE_NOT_FOUND') from exc
        _require_active_zone(target_zone)

    moving_zone = target_zone.pk != location.zone_id
    if moving_zone:
        location.zone = target_zone

    if 'priority' in fields and fields['priority'] is not None:
        new_priority = int(fields['priority'])
        if new_priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if location.status == DeliveryLocation.Status.ACTIVE:
            if moving_zone or new_priority != location.priority:
                # When staying in zone, use swap helper for conflicts.
                if not moving_zone:
                    location.save()
                    return set_location_priority(location, new_priority)
                ensure_active_location_priority_available(
                    target_zone,
                    new_priority,
                    exclude_location_id=location.pk,
                )
        location.priority = new_priority
    elif moving_zone and location.status == DeliveryLocation.Status.ACTIVE:
        # Keep priority if free; otherwise allocate next free in new zone.
        try:
            ensure_active_location_priority_available(
                target_zone,
                location.priority,
                exclude_location_id=location.pk,
            )
        except DeliveryZoneError:
            location.priority = allocate_location_priority(target_zone)

    location.save()
    return location


@transaction.atomic
def move_location_to_zone(location: DeliveryLocation, *, zone_public_id) -> DeliveryLocation:
    return update_location(location, zone_public_id=zone_public_id)


@transaction.atomic
def deactivate_location(location: DeliveryLocation) -> DeliveryLocation:
    location.status = DeliveryLocation.Status.INACTIVE
    location.save(update_fields=['status', 'updated_at'])
    return location


@transaction.atomic
def delete_location_if_empty(location: DeliveryLocation) -> None:
    if location.customers.exists():
        raise DeliveryZoneError(
            'Cannot delete a location that still has assigned customers. Reassign them first.',
            code='LOCATION_HAS_CUSTOMERS',
        )
    location.delete()
