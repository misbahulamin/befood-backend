from django.conf import settings
from django.db import transaction

from delivery_zones.models import DeliveryLocation, DeliverySubLocation
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.sub_locations import get_default_sub_location
from user_management.models import CustomerProfile


def legacy_location_assign_enabled() -> bool:
    return bool(getattr(settings, 'DELIVERY_SUB_LOCATION_LEGACY_LOCATION_ASSIGN', True))


def resolve_operational_sub_location(
    customer: CustomerProfile,
) -> DeliverySubLocation | None:
    """Return the customer's operational sub-location (source of truth)."""
    return getattr(customer, 'delivery_sub_location', None)


def resolve_operational_location(customer: CustomerProfile) -> DeliveryLocation | None:
    """Return derived location from sub-location; Bridge falls back to mirrored FK."""
    sub = resolve_operational_sub_location(customer)
    if sub is not None:
        return sub.location
    return customer.delivery_location


def derived_zone(customer: CustomerProfile):
    location = resolve_operational_location(customer)
    if location is None:
        return None
    return location.zone


def location_summary(location: DeliveryLocation | None) -> dict | None:
    if location is None:
        return None
    return {
        'public_id': str(location.public_id),
        'name': location.name,
        'priority': location.priority,
        'status': location.status,
    }


def zone_summary_from_location(location: DeliveryLocation | None) -> dict | None:
    if location is None:
        return None
    zone = location.zone
    return {
        'public_id': str(zone.public_id),
        'name': zone.name,
        'code': zone.code,
        'priority': zone.priority,
        'status': zone.status,
    }


def sub_location_summary(sub: DeliverySubLocation | None) -> dict | None:
    if sub is None:
        return None
    return {
        'public_id': str(sub.public_id),
        'name': sub.name,
        'priority': sub.priority,
        'status': sub.status,
        'is_default': bool(sub.is_default),
    }


def customer_delivery_hierarchy(customer: CustomerProfile) -> dict:
    sub = resolve_operational_sub_location(customer)
    location = resolve_operational_location(customer)
    return {
        'delivery_sub_location': sub_location_summary(sub),
        'delivery_location': location_summary(location),
        'delivery_zone': zone_summary_from_location(location),
    }


@transaction.atomic
def assign_customer_sub_location(
    customer: CustomerProfile,
    *,
    sub_location_public_id,
) -> CustomerProfile:
    if sub_location_public_id is None or sub_location_public_id == '':
        return clear_customer_sub_location(customer)

    try:
        sub = DeliverySubLocation.objects.select_related(
            'location', 'location__zone'
        ).get(public_id=sub_location_public_id)
    except DeliverySubLocation.DoesNotExist as exc:
        raise DeliveryZoneError(
            'Delivery sub-location not found.',
            code='SUB_LOCATION_NOT_FOUND',
        ) from exc

    if sub.status != DeliverySubLocation.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot assign an inactive sub-location.',
            code='SUB_LOCATION_INACTIVE',
        )
    if sub.location.status != DeliveryLocation.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot assign a sub-location under an inactive location.',
            code='LOCATION_INACTIVE',
        )
    if sub.location.zone.status != sub.location.zone.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot assign a sub-location in an inactive zone.',
            code='ZONE_INACTIVE',
        )

    customer.delivery_sub_location = sub
    # Bridge: keep mirrored parent location populated for old readers.
    customer.delivery_location = sub.location
    customer.save(
        update_fields=['delivery_sub_location', 'delivery_location', 'updated_at']
    )
    return customer


@transaction.atomic
def clear_customer_sub_location(customer: CustomerProfile) -> CustomerProfile:
    customer.delivery_sub_location = None
    customer.delivery_location = None
    customer.save(
        update_fields=['delivery_sub_location', 'delivery_location', 'updated_at']
    )
    return customer


@transaction.atomic
def assign_customer_location(
    customer: CustomerProfile,
    *,
    location_public_id,
) -> CustomerProfile:
    """Legacy location assign — Bridge maps to default sub-location when enabled."""
    if location_public_id is None or location_public_id == '':
        return clear_customer_sub_location(customer)

    if not legacy_location_assign_enabled():
        raise DeliveryZoneError(
            'Assigning by delivery_location_public_id alone is no longer supported. '
            'Send delivery_sub_location_public_id instead.',
            code='LEGACY_LOCATION_ASSIGN_DISABLED',
        )

    try:
        location = DeliveryLocation.objects.select_related('zone').get(
            public_id=location_public_id
        )
    except DeliveryLocation.DoesNotExist as exc:
        raise DeliveryZoneError('Delivery location not found.', code='LOCATION_NOT_FOUND') from exc

    if location.status != DeliveryLocation.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot assign an inactive location.',
            code='LOCATION_INACTIVE',
        )
    if location.zone.status != location.zone.Status.ACTIVE:
        raise DeliveryZoneError(
            'Cannot assign a location in an inactive zone.',
            code='ZONE_INACTIVE',
        )

    default_sub = get_default_sub_location(location)
    if default_sub is None:
        raise DeliveryZoneError(
            'Location has no default sub-location for legacy assignment.',
            code='DEFAULT_SUB_LOCATION_MISSING',
        )
    return assign_customer_sub_location(
        customer, sub_location_public_id=default_sub.public_id
    )


@transaction.atomic
def clear_customer_location(customer: CustomerProfile) -> CustomerProfile:
    return clear_customer_sub_location(customer)
