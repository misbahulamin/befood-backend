from django.db import transaction
from django.db.models import Q

from delivery_zones.models import DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.priority import (
    allocate_zone_priority,
    ensure_active_zone_priority_available,
)
from user_management.models import RiderProfile


def get_zone_by_public_id(public_id) -> DeliveryZone:
    try:
        return DeliveryZone.objects.select_related(
            'assigned_delivery_man',
            'assigned_delivery_man__user',
        ).get(public_id=public_id)
    except DeliveryZone.DoesNotExist as exc:
        raise DeliveryZoneError('Delivery zone not found.', code='ZONE_NOT_FOUND') from exc


def list_zones(*, status: str | None = None, q: str | None = None):
    qs = DeliveryZone.objects.select_related(
        'assigned_delivery_man',
        'assigned_delivery_man__user',
    ).order_by('priority', 'name', 'id')
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return qs


def _normalize_code(code: str) -> str:
    value = (code or '').strip().lower().replace(' ', '-')
    if not value:
        raise DeliveryZoneError('code is required.', code='CODE_REQUIRED')
    return value


def _normalize_name(name: str) -> str:
    value = (name or '').strip()
    if not value:
        raise DeliveryZoneError('name is required.', code='NAME_REQUIRED')
    return value


def _resolve_approved_rider(rider_public_id) -> RiderProfile:
    if rider_public_id is None:
        raise DeliveryZoneError(
            'delivery_man_public_id is required.',
            code='DELIVERY_MAN_REQUIRED',
        )
    try:
        rider = RiderProfile.objects.select_related('user').get(public_id=rider_public_id)
    except RiderProfile.DoesNotExist as exc:
        raise DeliveryZoneError(
            'Delivery Man not found.',
            code='DELIVERY_MAN_NOT_FOUND',
        ) from exc
    if not rider.is_verified or rider.approval_status != RiderProfile.ApprovalStatus.APPROVED:
        raise DeliveryZoneError(
            'Only approved Delivery Men can be assigned to a zone.',
            code='DELIVERY_MAN_NOT_APPROVED',
        )
    return rider


@transaction.atomic
def create_zone(
    *,
    name: str,
    code: str,
    priority: int | None = None,
    status: str = DeliveryZone.Status.ACTIVE,
    delivery_man_public_id=None,
) -> DeliveryZone:
    name = _normalize_name(name)
    code = _normalize_code(code)
    if DeliveryZone.objects.filter(code=code).exists():
        raise DeliveryZoneError('A zone with this code already exists.', code='CODE_DUPLICATE')

    status_value = status or DeliveryZone.Status.ACTIVE
    if status_value not in DeliveryZone.Status.values:
        raise DeliveryZoneError('Invalid zone status.', code='INVALID_STATUS')

    if priority is None:
        priority = allocate_zone_priority()
    else:
        priority = int(priority)
        if priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if status_value == DeliveryZone.Status.ACTIVE:
            ensure_active_zone_priority_available(priority)

    zone = DeliveryZone.objects.create(
        name=name,
        code=code,
        priority=priority,
        status=status_value,
    )
    if delivery_man_public_id is not None:
        zone = assign_delivery_man(zone, delivery_man_public_id=delivery_man_public_id)
    return zone


@transaction.atomic
def update_zone(zone: DeliveryZone, **fields) -> DeliveryZone:
    if 'name' in fields and fields['name'] is not None:
        zone.name = _normalize_name(fields['name'])
    if 'code' in fields and fields['code'] is not None:
        code = _normalize_code(fields['code'])
        if DeliveryZone.objects.filter(code=code).exclude(pk=zone.pk).exists():
            raise DeliveryZoneError('A zone with this code already exists.', code='CODE_DUPLICATE')
        zone.code = code
    if 'status' in fields and fields['status'] is not None:
        status_value = fields['status']
        if status_value not in DeliveryZone.Status.values:
            raise DeliveryZoneError('Invalid zone status.', code='INVALID_STATUS')
        zone.status = status_value
    if 'priority' in fields and fields['priority'] is not None:
        priority = int(fields['priority'])
        if priority < 1:
            raise DeliveryZoneError('priority must be >= 1.', code='INVALID_PRIORITY')
        if zone.status == DeliveryZone.Status.ACTIVE or fields.get('status') == DeliveryZone.Status.ACTIVE:
            ensure_active_zone_priority_available(priority, exclude_zone_id=zone.pk)
        zone.priority = priority

    zone.save()

    if 'delivery_man_public_id' in fields:
        rider_id = fields['delivery_man_public_id']
        if rider_id is None or rider_id == '':
            zone = clear_delivery_man(zone)
        else:
            zone = assign_delivery_man(zone, delivery_man_public_id=rider_id)
    return zone


@transaction.atomic
def assign_delivery_man(zone: DeliveryZone, *, delivery_man_public_id) -> DeliveryZone:
    rider = _resolve_approved_rider(delivery_man_public_id)
    conflict = (
        DeliveryZone.objects.select_for_update()
        .filter(assigned_delivery_man=rider)
        .exclude(pk=zone.pk)
        .first()
    )
    if conflict is not None:
        raise DeliveryZoneError(
            f'Delivery Man is already assigned to zone "{conflict.name}".',
            code='DELIVERY_MAN_ALREADY_ASSIGNED',
        )
    zone.assigned_delivery_man = rider
    zone.save(update_fields=['assigned_delivery_man', 'updated_at'])
    return zone


@transaction.atomic
def clear_delivery_man(zone: DeliveryZone) -> DeliveryZone:
    zone.assigned_delivery_man = None
    zone.save(update_fields=['assigned_delivery_man', 'updated_at'])
    return zone


@transaction.atomic
def deactivate_zone(zone: DeliveryZone) -> DeliveryZone:
    zone.status = DeliveryZone.Status.INACTIVE
    zone.save(update_fields=['status', 'updated_at'])
    return zone


@transaction.atomic
def delete_zone_if_empty(zone: DeliveryZone) -> None:
    if zone.locations.exists():
        raise DeliveryZoneError(
            'Cannot delete a zone that still has locations. Move or delete locations first.',
            code='ZONE_HAS_LOCATIONS',
        )
    zone.delete()


def zone_for_rider(rider: RiderProfile) -> DeliveryZone | None:
    return (
        DeliveryZone.objects.select_related('assigned_delivery_man')
        .filter(assigned_delivery_man=rider)
        .first()
    )
