from django.db import transaction

from user_management.models import (
    CustomerDeliveryPlace,
    MealDeliveryDayOverride,
    MealDeliveryPreference,
)
from user_management.services.profile_completion import update_profile_completion

MAX_ACTIVE_DELIVERY_PLACES = 10


class DeliveryPlaceError(Exception):
    """Domain error for delivery place operations."""

    def __init__(self, message, code='delivery_place_error'):
        super().__init__(message)
        self.code = code


def _owned_place_qs(customer_profile):
    return CustomerDeliveryPlace.objects.filter(customer_profile=customer_profile)


def get_place_or_error(customer_profile, public_id):
    try:
        return _owned_place_qs(customer_profile).get(public_id=public_id)
    except CustomerDeliveryPlace.DoesNotExist as exc:
        raise DeliveryPlaceError('Delivery place not found.', code='not_found') from exc


def create_delivery_place(customer_profile, *, label, full_address, **address_fields):
    label = (label or '').strip()
    full_address = (full_address or '').strip()
    if not label:
        raise DeliveryPlaceError('Label is required.', code='validation')
    if not full_address:
        raise DeliveryPlaceError('Full address is required.', code='validation')

    active_count = _owned_place_qs(customer_profile).filter(is_active=True).count()
    if active_count >= MAX_ACTIVE_DELIVERY_PLACES:
        raise DeliveryPlaceError(
            f'Maximum of {MAX_ACTIVE_DELIVERY_PLACES} active delivery places allowed.',
            code='soft_cap',
        )

    place = CustomerDeliveryPlace.objects.create(
        customer_profile=customer_profile,
        label=label,
        full_address=full_address,
        city=address_fields.get('city') or 'Dhaka',
        area=address_fields.get('area') or '',
        building_name=address_fields.get('building_name') or '',
        floor=address_fields.get('floor') or '',
        flat_number=address_fields.get('flat_number') or '',
        landmark=address_fields.get('landmark') or '',
        latitude=address_fields.get('latitude'),
        longitude=address_fields.get('longitude'),
        is_active=True,
    )
    update_profile_completion(customer_profile)
    return place


def update_delivery_place(place, **fields):
    if 'label' in fields:
        label = (fields['label'] or '').strip()
        if not label:
            raise DeliveryPlaceError('Label is required.', code='validation')
        place.label = label
    if 'full_address' in fields:
        full_address = (fields['full_address'] or '').strip()
        if not full_address:
            raise DeliveryPlaceError('Full address is required.', code='validation')
        place.full_address = full_address

    for key in (
        'city',
        'area',
        'building_name',
        'floor',
        'flat_number',
        'landmark',
        'latitude',
        'longitude',
        'is_active',
    ):
        if key in fields and fields[key] is not None:
            setattr(place, key, fields[key])
        elif key in fields and key in ('latitude', 'longitude', 'is_active'):
            setattr(place, key, fields[key])

    place.save()
    update_profile_completion(place.customer_profile)
    return place


def _place_in_use(place) -> bool:
    prefs = MealDeliveryPreference.objects.filter(customer_profile_id=place.customer_profile_id).first()
    if prefs and (prefs.lunch_place_id == place.pk or prefs.dinner_place_id == place.pk):
        return True
    return MealDeliveryDayOverride.objects.filter(place=place).exists()


def delete_delivery_place(place):
    if _place_in_use(place):
        raise DeliveryPlaceError(
            'Place is used by lunch/dinner preferences or a day override. '
            'Reassign those first.',
            code='in_use',
        )
    profile = place.customer_profile
    place.delete()
    update_profile_completion(profile)


def ensure_place_owned(customer_profile, place: CustomerDeliveryPlace | None):
    if place is None:
        return None
    if place.customer_profile_id != customer_profile.id:
        raise DeliveryPlaceError('Delivery place not found.', code='not_found')
    if not place.is_active:
        raise DeliveryPlaceError('Delivery place is inactive.', code='inactive')
    return place
