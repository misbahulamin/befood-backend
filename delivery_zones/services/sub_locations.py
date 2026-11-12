from django.db import transaction
from django.db.models import Count, Q

from delivery_zones.models import DeliveryLocation, DeliverySubLocation
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.priority import (
    allocate_sub_location_priority,
    ensure_active_sub_location_priority_available,
    set_sub_location_priority,
)


def get_sub_location_by_public_id(public_id) -> DeliverySubLocation:
    try:
        return (
            DeliverySubLocation.objects.select_related(
                'location',
                'location__zone',
                'location__zone__assigned_delivery_man',
                'location__zone__assigned_delivery_man__user',
            )
            .annotate(customer_count=Count('customers', distinct=True))
            .get(public_id=public_id)
        )
    except DeliverySubLocation.DoesNotExist as exc:
        raise DeliveryZoneError(
            'Delivery sub-location not found.',
            code='SUB_LOCATION_NOT_FOUND',
        ) from exc


def list_sub_locations(
    *,
    location_public_id=None,
    zone_public_id=None,
    status: str | None = None,
    q: str | None = None,
):
    qs = (
        DeliverySubLocation.objects.select_related(
            'location',
            'location__zone',
            'location__zone__assigned_delivery_man',
            'location__zone__assigned_delivery_man__user',
        )
        .annotate(customer_count=Count('customers', distinct=True))
        .order_by(
            'location__zone__priority',
            'location__priority',
            'priority',
            'name',
            'id',
        )
    )
    if location_public_id:
        qs = qs.filter(location__public_id=location_public_id)
    if zone_public_id:
        qs = qs.filter(location__zone__public_id=zone_public_id)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(location__name__icontains=q)
            | Q(location__zone__name__icontains=q)
        )
    return qs


def _normalize_name(name: str) -> str:
    value = (name or '').strip()
    if not value:
        raise DeliveryZoneError('name is required.', code='NAME_REQUIRED')
    return value


def _require_active_location(location: DeliveryLocation) -> None:
    if location.status != DeliveryLocation.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot use an inactive location for sub-location assignment.',
            code='LOCATION_INACTIVE',
        )
    if location.zone.status != location.zone.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot use a location in an inactive zone.',
            code='ZONE_INACTIVE',
        )


def _apply_centroid(sub: DeliverySubLocation, fields: dict) -> None:
    has_lat = 'centroid_latitude' in fields
    has_lng = 'centroid_longitude' in fields
    if not has_lat and not has_lng:
        return
    latitude = fields.get('centroid_latitude') if has_lat else sub.centroid_latitude
    longitude = fields.get('centroid_longitude') if has_lng else sub.centroid_longitude
    if (latitude is None) != (longitude is None):
        raise DeliveryZoneError(
            'centroid_latitude and centroid_longitude must both be set or both be empty.',
            code='INVALID_COORDINATES',
        )
    sub.centroid_latitude = latitude
    sub.centroid_longitude = longitude


def get_default_sub_location(location: DeliveryLocation) -> DeliverySubLocation | None:
    return (
        DeliverySubLocation.objects.filter(location=location, is_default=True)
        .order_by('priority', 'id')
        .first()
    )


@transaction.atomic
def create_sub_location(
    *,
    name: str,
    location_public_id,
    priority: int | None = None,
    status: str = DeliverySubLocation.Status.ACTIVE,
    is_default: bool = False,
    centroid_latitude=None,
    centroid_longitude=None,
) -> DeliverySubLocation:
    name = _normalize_name(name)
    try:
        location = (
            DeliveryLocation.objects.select_for_update()
            .select_related('zone')
            .get(public_id=location_public_id)
        )
    except DeliveryLocation.DoesNotExist as exc:
        raise DeliveryZoneError('Delivery location not found.', code='LOCATION_NOT_FOUND') from exc
    _require_active_location(location)

    status_value = status or DeliverySubLocation.Status.ACTIVE
    if status_value not in DeliverySubLocation.Status.values:
        raise DeliveryZoneError('Invalid sub-location status.', code='INVALID_STATUS')

    if priority is None:
        priority = allocate_sub_location_priority(location)
    else:
        priority = int(priority)
        if priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if status_value == DeliverySubLocation.Status.ACTIVE:
            ensure_active_sub_location_priority_available(location, priority)

    if is_default and DeliverySubLocation.objects.filter(
        location=location, is_default=True
    ).exists():
        raise DeliveryZoneError(
            'This location already has a default sub-location.',
            code='DEFAULT_SUB_LOCATION_EXISTS',
        )

    sub = DeliverySubLocation(
        name=name,
        location=location,
        priority=priority,
        status=status_value,
        is_default=bool(is_default),
    )
    _apply_centroid(
        sub,
        {
            'centroid_latitude': centroid_latitude,
            'centroid_longitude': centroid_longitude,
        },
    )
    sub.save()
    return sub


@transaction.atomic
def update_sub_location(sub_location: DeliverySubLocation, **fields) -> DeliverySubLocation:
    sub_location = (
        DeliverySubLocation.objects.select_for_update()
        .select_related('location', 'location__zone')
        .get(pk=sub_location.pk)
    )

    if 'name' in fields and fields['name'] is not None:
        sub_location.name = _normalize_name(fields['name'])

    if 'status' in fields and fields['status'] is not None:
        status_value = fields['status']
        if status_value not in DeliverySubLocation.Status.values:
            raise DeliveryZoneError('Invalid sub-location status.', code='INVALID_STATUS')
        sub_location.status = status_value

    if 'is_default' in fields and fields['is_default'] is not None:
        becoming_default = bool(fields['is_default'])
        if becoming_default and not sub_location.is_default:
            other = (
                DeliverySubLocation.objects.select_for_update()
                .filter(location_id=sub_location.location_id, is_default=True)
                .exclude(pk=sub_location.pk)
                .first()
            )
            if other is not None:
                other.is_default = False
                other.save(update_fields=['is_default', 'updated_at'])
        sub_location.is_default = becoming_default

    target_location = sub_location.location
    if 'location_public_id' in fields and fields['location_public_id'] is not None:
        try:
            target_location = (
                DeliveryLocation.objects.select_for_update()
                .select_related('zone')
                .get(public_id=fields['location_public_id'])
            )
        except DeliveryLocation.DoesNotExist as exc:
            raise DeliveryZoneError(
                'Delivery location not found.',
                code='LOCATION_NOT_FOUND',
            ) from exc
        _require_active_location(target_location)

    moving_location = target_location.pk != sub_location.location_id
    if moving_location:
        if sub_location.is_default and DeliverySubLocation.objects.filter(
            location=target_location, is_default=True
        ).exists():
            raise DeliveryZoneError(
                'Target location already has a default sub-location.',
                code='DEFAULT_SUB_LOCATION_EXISTS',
            )
        sub_location.location = target_location

    _apply_centroid(sub_location, fields)

    if 'priority' in fields and fields['priority'] is not None:
        new_priority = int(fields['priority'])
        if new_priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if sub_location.status == DeliverySubLocation.Status.ACTIVE:
            if moving_location or new_priority != sub_location.priority:
                if not moving_location:
                    sub_location.save()
                    return set_sub_location_priority(sub_location, new_priority)
                ensure_active_sub_location_priority_available(
                    target_location,
                    new_priority,
                    exclude_sub_location_id=sub_location.pk,
                )
        sub_location.priority = new_priority
    elif moving_location and sub_location.status == DeliverySubLocation.Status.ACTIVE:
        try:
            ensure_active_sub_location_priority_available(
                target_location,
                sub_location.priority,
                exclude_sub_location_id=sub_location.pk,
            )
        except DeliveryZoneError:
            sub_location.priority = allocate_sub_location_priority(target_location)

    sub_location.save()
    return sub_location


@transaction.atomic
def move_sub_location_to_location(
    sub_location: DeliverySubLocation, *, location_public_id
) -> DeliverySubLocation:
    return update_sub_location(sub_location, location_public_id=location_public_id)


@transaction.atomic
def deactivate_sub_location(sub_location: DeliverySubLocation) -> DeliverySubLocation:
    sub_location.status = DeliverySubLocation.Status.INACTIVE
    sub_location.save(update_fields=['status', 'updated_at'])
    return sub_location


@transaction.atomic
def delete_sub_location_if_empty(sub_location: DeliverySubLocation) -> None:
    if sub_location.customers.exists():
        raise DeliveryZoneError(
            'Cannot delete a sub-location that still has assigned customers. '
            'Reassign them first.',
            code='SUB_LOCATION_HAS_CUSTOMERS',
        )
    sub_location.delete()
