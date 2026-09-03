from django.db import transaction

from user_management.models import (
    CustomerDeliveryPlace,
    CustomerLocationSettings,
    MealDeliveryDayOverride,
    MealDeliveryPreference,
)
from user_management.services.location_service import (
    GEO_LOCATION_SOURCES,
    calculate_distance,
    normalize_accuracy,
    requires_coordinates,
    validate_location_coordinates,
)
from user_management.services.profile_completion import update_profile_completion

# Legacy constant kept for imports/tests that still reference the symbol name.
# Runtime limit comes from CustomerLocationSettings.max_active_delivery_places.
MAX_ACTIVE_DELIVERY_PLACES = 3

ADDRESS_LIMIT_REACHED = 'ADDRESS_LIMIT_REACHED'
LOCATION_ALREADY_EXISTS = 'LOCATION_ALREADY_EXISTS'


class DeliveryPlaceError(Exception):
    """Domain error for delivery place operations."""

    def __init__(self, message, code='delivery_place_error'):
        super().__init__(message)
        self.code = code


def _owned_place_qs(customer_profile):
    return CustomerDeliveryPlace.objects.filter(customer_profile=customer_profile)


def get_max_active_delivery_places() -> int:
    return int(CustomerLocationSettings.load().max_active_delivery_places)


def get_duplicate_radius_km():
    return CustomerLocationSettings.load().duplicate_radius_km


def get_place_or_error(customer_profile, public_id):
    try:
        return _owned_place_qs(customer_profile).get(public_id=public_id)
    except CustomerDeliveryPlace.DoesNotExist as exc:
        raise DeliveryPlaceError('Delivery place not found.', code='not_found') from exc


def _resolve_address_text(*, full_address=None, formatted_address=None) -> str:
    text = (full_address or '').strip()
    if text:
        return text
    return (formatted_address or '').strip()


def _assert_geo_payload(*, location_source, latitude, longitude, full_address, formatted_address):
    source = (location_source or '').strip()
    if not requires_coordinates(source):
        return
    if latitude is None or longitude is None:
        raise DeliveryPlaceError(
            'latitude and longitude are required for this location_source.',
            code='validation',
        )
    validate_location_coordinates(latitude, longitude)
    if not _resolve_address_text(full_address=full_address, formatted_address=formatted_address):
        raise DeliveryPlaceError(
            'full_address or formatted_address is required for this location_source.',
            code='validation',
        )


def find_nearby_active_place(
    customer_profile,
    *,
    latitude,
    longitude,
    exclude_place_id=None,
):
    """Return the first active place within duplicate radius, or None."""
    if latitude is None or longitude is None:
        return None
    lat, lng = validate_location_coordinates(latitude, longitude)
    radius = get_duplicate_radius_km()
    qs = _owned_place_qs(customer_profile).filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )
    if exclude_place_id is not None:
        qs = qs.exclude(pk=exclude_place_id)

    for other in qs:
        distance = calculate_distance(lat, lng, other.latitude, other.longitude)
        if distance <= radius:
            return other
    return None


def assert_not_duplicate_location(
    customer_profile,
    *,
    latitude,
    longitude,
    exclude_place_id=None,
):
    """Reject when within duplicate radius of another active place with coordinates."""
    other = find_nearby_active_place(
        customer_profile,
        latitude=latitude,
        longitude=longitude,
        exclude_place_id=exclude_place_id,
    )
    if other is not None:
        raise DeliveryPlaceError(
            'A delivery address already exists near this location.',
            code=LOCATION_ALREADY_EXISTS,
        )


def create_delivery_place(customer_profile, *, label, full_address, **address_fields):
    label = (label or '').strip()
    formatted_address = (address_fields.get('formatted_address') or '').strip()
    full_address = _resolve_address_text(
        full_address=full_address,
        formatted_address=formatted_address,
    )
    if not label:
        raise DeliveryPlaceError('Label is required.', code='validation')
    if not full_address:
        raise DeliveryPlaceError('Full address is required.', code='validation')

    location_source = (address_fields.get('location_source') or '').strip()
    latitude = address_fields.get('latitude')
    longitude = address_fields.get('longitude')
    _assert_geo_payload(
        location_source=location_source,
        latitude=latitude,
        longitude=longitude,
        full_address=full_address,
        formatted_address=formatted_address,
    )
    if latitude is not None and longitude is not None:
        latitude, longitude = validate_location_coordinates(latitude, longitude)
        assert_not_duplicate_location(
            customer_profile,
            latitude=latitude,
            longitude=longitude,
        )

    max_places = get_max_active_delivery_places()
    active_count = _owned_place_qs(customer_profile).filter(is_active=True).count()
    if active_count >= max_places:
        raise DeliveryPlaceError(
            f'Maximum of {max_places} active delivery places allowed.',
            code=ADDRESS_LIMIT_REACHED,
        )

    accuracy = address_fields.get('location_accuracy')
    if accuracy is not None:
        accuracy = normalize_accuracy(accuracy)

    is_verified = bool(address_fields.get('is_verified_location'))
    if location_source in GEO_LOCATION_SOURCES and latitude is not None and longitude is not None:
        is_verified = True

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
        latitude=latitude,
        longitude=longitude,
        location_source=location_source,
        location_accuracy=accuracy,
        formatted_address=formatted_address or full_address,
        is_verified_location=is_verified,
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

    formatted_address = fields.get('formatted_address', place.formatted_address)
    if 'formatted_address' in fields:
        formatted_address = (fields['formatted_address'] or '').strip()
        place.formatted_address = formatted_address

    if 'full_address' in fields:
        full_address = _resolve_address_text(
            full_address=fields['full_address'],
            formatted_address=formatted_address,
        )
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
        'location_source',
        'is_active',
        'is_verified_location',
    ):
        if key in fields and fields[key] is not None:
            if key == 'location_source':
                place.location_source = (fields[key] or '').strip()
            else:
                setattr(place, key, fields[key])
        elif key in fields and key in (
            'latitude',
            'longitude',
            'is_active',
            'is_verified_location',
            'location_source',
        ):
            setattr(place, key, fields[key] if key != 'location_source' else (fields[key] or ''))

    if 'location_accuracy' in fields:
        accuracy = fields['location_accuracy']
        place.location_accuracy = normalize_accuracy(accuracy) if accuracy is not None else None

    _assert_geo_payload(
        location_source=place.location_source,
        latitude=place.latitude,
        longitude=place.longitude,
        full_address=place.full_address,
        formatted_address=place.formatted_address,
    )

    coords_changing = 'latitude' in fields or 'longitude' in fields
    if place.latitude is not None and place.longitude is not None and (
        coords_changing or requires_coordinates(place.location_source)
    ):
        lat, lng = validate_location_coordinates(place.latitude, place.longitude)
        place.latitude = lat
        place.longitude = lng
        if coords_changing or requires_coordinates(place.location_source):
            assert_not_duplicate_location(
                place.customer_profile,
                latitude=lat,
                longitude=lng,
                exclude_place_id=place.pk,
            )
        if place.location_source in GEO_LOCATION_SOURCES:
            place.is_verified_location = True

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
