from django.db import transaction
from django.db.models import Max

from delivery_zones.models import DeliveryLocation, DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError


def allocate_zone_priority() -> int:
    current = (
        DeliveryZone.objects.filter(status=DeliveryZone.Status.ACTIVE)
        .aggregate(m=Max('priority'))
        .get('m')
    )
    return int(current or 0) + 1


def allocate_location_priority(zone: DeliveryZone) -> int:
    current = (
        DeliveryLocation.objects.filter(zone=zone, status=DeliveryLocation.Status.ACTIVE)
        .aggregate(m=Max('priority'))
        .get('m')
    )
    return int(current or 0) + 1


def ensure_active_zone_priority_available(priority: int, *, exclude_zone_id=None) -> None:
    qs = DeliveryZone.objects.filter(status=DeliveryZone.Status.ACTIVE, priority=priority)
    if exclude_zone_id is not None:
        qs = qs.exclude(pk=exclude_zone_id)
    if qs.exists():
        raise DeliveryZoneError(
            f'Active zone priority {priority} is already in use.',
            code='PRIORITY_CONFLICT',
        )


def ensure_active_location_priority_available(
    zone: DeliveryZone,
    priority: int,
    *,
    exclude_location_id=None,
) -> None:
    qs = DeliveryLocation.objects.filter(
        zone=zone,
        status=DeliveryLocation.Status.ACTIVE,
        priority=priority,
    )
    if exclude_location_id is not None:
        qs = qs.exclude(pk=exclude_location_id)
    if qs.exists():
        raise DeliveryZoneError(
            f'Active location priority {priority} is already in use in this zone.',
            code='PRIORITY_CONFLICT',
        )


@transaction.atomic
def set_zone_priority(zone: DeliveryZone, new_priority: int) -> DeliveryZone:
    """Set zone priority, swapping with the occupant if needed."""
    new_priority = int(new_priority)
    if new_priority < 1:
        raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')

    zone = DeliveryZone.objects.select_for_update().get(pk=zone.pk)
    if zone.priority == new_priority:
        return zone

    other = (
        DeliveryZone.objects.select_for_update()
        .filter(status=DeliveryZone.Status.ACTIVE, priority=new_priority)
        .exclude(pk=zone.pk)
        .first()
    )
    if other is None:
        zone.priority = new_priority
        zone.save(update_fields=['priority', 'updated_at'])
        return zone

    old_priority = zone.priority
    # Temporary unique-safe swap using a high unused priority.
    temp = allocate_zone_priority() + 1000
    other.priority = temp
    other.save(update_fields=['priority', 'updated_at'])
    zone.priority = new_priority
    zone.save(update_fields=['priority', 'updated_at'])
    other.priority = old_priority
    other.save(update_fields=['priority', 'updated_at'])
    return zone


@transaction.atomic
def set_location_priority(location: DeliveryLocation, new_priority: int) -> DeliveryLocation:
    """Set location priority within its zone, swapping with the occupant if needed."""
    new_priority = int(new_priority)
    if new_priority < 1:
        raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')

    location = DeliveryLocation.objects.select_for_update().select_related('zone').get(
        pk=location.pk
    )
    if location.priority == new_priority:
        return location

    other = (
        DeliveryLocation.objects.select_for_update()
        .filter(
            zone_id=location.zone_id,
            status=DeliveryLocation.Status.ACTIVE,
            priority=new_priority,
        )
        .exclude(pk=location.pk)
        .first()
    )
    if other is None:
        location.priority = new_priority
        location.save(update_fields=['priority', 'updated_at'])
        return location

    old_priority = location.priority
    temp = allocate_location_priority(location.zone) + 1000
    other.priority = temp
    other.save(update_fields=['priority', 'updated_at'])
    location.priority = new_priority
    location.save(update_fields=['priority', 'updated_at'])
    other.priority = old_priority
    other.save(update_fields=['priority', 'updated_at'])
    return location


@transaction.atomic
def reorder_location_priorities(zone: DeliveryZone, items: list[dict]) -> list[DeliveryLocation]:
    """Rewrite every location priority in one zone to a dense 1..n sequence.

    Active (zone, priority) is unique, so rows are parked on temporary priorities
    before the final numbers are written.
    """
    zone = DeliveryZone.objects.select_for_update().get(pk=zone.pk)
    locations = list(
        DeliveryLocation.objects.select_for_update().filter(zone=zone).order_by('priority', 'id')
    )
    by_public_id = {loc.public_id: loc for loc in locations}

    if len(items) != len(locations):
        raise DeliveryZoneError(
            'Reorder must include every location in the zone.',
            code='INVALID_REORDER',
        )

    seen_ids: set = set()
    seen_priorities: set[int] = set()
    assigned: list[tuple[DeliveryLocation, int]] = []
    for item in items:
        public_id = item['public_id']
        priority = int(item['priority'])
        if public_id in seen_ids or priority in seen_priorities:
            raise DeliveryZoneError(
                'Reorder priorities and locations must be unique.',
                code='INVALID_REORDER',
            )
        location = by_public_id.get(public_id)
        if location is None:
            raise DeliveryZoneError(
                'Reorder must include every location in the zone.',
                code='INVALID_REORDER',
            )
        if priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        seen_ids.add(public_id)
        seen_priorities.add(priority)
        assigned.append((location, priority))

    expected = set(range(1, len(locations) + 1))
    if seen_priorities != expected:
        raise DeliveryZoneError(
            'Priorities must be the dense sequence 1..n for this zone.',
            code='INVALID_REORDER',
        )

    max_priority = max((loc.priority for loc in locations), default=0)
    for index, location in enumerate(locations):
        if location.status != DeliveryLocation.Status.ACTIVE:
            continue
        location.priority = max_priority + 1000 + index + 1
        location.save(update_fields=['priority', 'updated_at'])

    for location, priority in assigned:
        location.priority = priority
        location.save(update_fields=['priority', 'updated_at'])

    return list(
        DeliveryLocation.objects.filter(zone=zone).order_by('priority', 'name', 'id')
    )
