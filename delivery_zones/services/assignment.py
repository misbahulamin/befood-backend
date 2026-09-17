from django.db import transaction

from delivery_zones.models import DeliveryLocation
from delivery_zones.services.errors import DeliveryZoneError
from user_management.models import CustomerProfile


def resolve_operational_location(customer: CustomerProfile) -> DeliveryLocation | None:
    """Return the customer's operational location (phase 1: FK only; future: GPS match)."""
    return customer.delivery_location


def derived_zone(customer: CustomerProfile):
    location = resolve_operational_location(customer)
    if location is None:
        return None
    return location.zone


@transaction.atomic
def assign_customer_location(
    customer: CustomerProfile,
    *,
    location_public_id,
) -> CustomerProfile:
    if location_public_id is None or location_public_id == '':
        return clear_customer_location(customer)

    try:
        location = DeliveryLocation.objects.select_related('zone').get(public_id=location_public_id)
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

    customer.delivery_location = location
    customer.save(update_fields=['delivery_location', 'updated_at'])
    return customer


@transaction.atomic
def clear_customer_location(customer: CustomerProfile) -> CustomerProfile:
    customer.delivery_location = None
    customer.save(update_fields=['delivery_location', 'updated_at'])
    return customer


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
