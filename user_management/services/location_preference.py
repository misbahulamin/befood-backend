from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from service_area.models import ServiceAreaRequest
from user_management.models import CustomerLocationPreference, CustomerLocationSettings
from user_management.services.delivery_place import (
    DeliveryPlaceError,
    create_delivery_place,
    get_place_or_error,
)
from user_management.services.delivery_preference import set_meal_delivery_preferences
from user_management.services.location_service import (
    accuracy_warning_code,
    normalize_accuracy,
    validate_location_coordinates,
)


class LocationPreferenceError(Exception):
    def __init__(self, message, code='location_preference_error'):
        super().__init__(message)
        self.code = code


def get_or_create_location_preference(customer_profile) -> CustomerLocationPreference:
    pref, _ = CustomerLocationPreference.objects.get_or_create(
        customer_profile=customer_profile,
        defaults={'is_active': True},
    )
    return pref


def get_refresh_interval_hours() -> int:
    return int(CustomerLocationSettings.load().location_refresh_interval_hours)


def _freshness(detected_at):
    interval_hours = get_refresh_interval_hours()
    if detected_at is None:
        return {
            'can_refresh': True,
            'expires_at': None,
            'stale': True,
            'refresh_interval_hours': interval_hours,
        }
    expires_at = detected_at + timedelta(hours=interval_hours)
    now = timezone.now()
    stale = now >= expires_at
    return {
        'can_refresh': stale,
        'expires_at': expires_at,
        'stale': stale,
        'refresh_interval_hours': interval_hours,
    }


def serialize_location_preference(pref: CustomerLocationPreference | None) -> dict:
    if pref is None or (not pref.is_active and pref.saved_at is None and pref.detected_at is None):
        return {'exists': False}

    freshness = _freshness(pref.detected_at)
    place = pref.active_delivery_place
    saved_exists = pref.saved_latitude is not None and pref.saved_longitude is not None
    detected_exists = (
        pref.last_detected_latitude is not None and pref.last_detected_longitude is not None
    )

    return {
        'exists': True,
        'is_active': pref.is_active,
        'saved': {
            'exists': saved_exists,
            'address_id': str(place.public_id) if place_id_safe(place) else None,
            'latitude': pref.saved_latitude,
            'longitude': pref.saved_longitude,
            'location_name': pref.saved_location_name or None,
            'saved_at': pref.saved_at,
        },
        'detected': {
            'exists': detected_exists,
            'latitude': pref.last_detected_latitude,
            'longitude': pref.last_detected_longitude,
            'location_name': pref.last_detected_location_name or None,
            'accuracy': pref.last_detected_accuracy,
            'detected_at': pref.detected_at,
        },
        'can_refresh': freshness['can_refresh'],
        'expires_at': freshness['expires_at'],
        'stale': freshness['stale'],
        'refresh_interval_hours': freshness['refresh_interval_hours'],
    }


def place_id_safe(place) -> bool:
    return place is not None and getattr(place, 'public_id', None) is not None


def get_location_preference_payload(customer_profile) -> dict:
    try:
        pref = CustomerLocationPreference.objects.select_related('active_delivery_place').get(
            customer_profile=customer_profile
        )
    except CustomerLocationPreference.DoesNotExist:
        return {'exists': False}
    return serialize_location_preference(pref)


@transaction.atomic
def refresh_detected_location(
    customer_profile,
    *,
    latitude,
    longitude,
    accuracy=None,
    location_name: str | None = None,
    source: str = 'gps',
) -> tuple[CustomerLocationPreference, str | None]:
    lat, lng = validate_location_coordinates(latitude, longitude)
    acc = normalize_accuracy(accuracy) if accuracy is not None else None
    warning = accuracy_warning_code(acc)
    pref = get_or_create_location_preference(customer_profile)
    pref.last_detected_latitude = lat
    pref.last_detected_longitude = lng
    pref.last_detected_location_name = (location_name or '').strip()[:255]
    pref.last_detected_accuracy = acc
    pref.detected_at = timezone.now()
    pref.is_active = True
    pref.save(
        update_fields=[
            'last_detected_latitude',
            'last_detected_longitude',
            'last_detected_location_name',
            'last_detected_accuracy',
            'detected_at',
            'is_active',
            'updated_at',
        ]
    )
    # source currently informational for clients; detection analytics use fields above
    _ = source
    return pref, warning


def _apply_optional_meal_defaults(
    customer_profile,
    place,
    *,
    set_lunch_default: bool = False,
    set_dinner_default: bool = False,
    set_as_default_delivery_place: bool = False,
):
    """Meal defaults change only when explicit flags are true."""
    if set_as_default_delivery_place:
        set_lunch_default = True
        set_dinner_default = True
    if not set_lunch_default and not set_dinner_default:
        return
    kwargs = {}
    if set_lunch_default:
        kwargs['lunch_place'] = place
    if set_dinner_default:
        kwargs['dinner_place'] = place
    set_meal_delivery_preferences(customer_profile, **kwargs)


@transaction.atomic
def save_detected_as_place(
    customer_profile,
    *,
    label,
    full_address=None,
    formatted_address=None,
    latitude=None,
    longitude=None,
    location_source='gps',
    location_accuracy=None,
    city='Dhaka',
    area='',
    building_name='',
    floor='',
    flat_number='',
    landmark='',
    set_lunch_default: bool = False,
    set_dinner_default: bool = False,
    set_as_default_delivery_place: bool = False,
    set_as_active: bool = True,
) -> tuple[object, CustomerLocationPreference, str | None]:
    pref = get_or_create_location_preference(customer_profile)

    if latitude is None:
        latitude = pref.last_detected_latitude
    if longitude is None:
        longitude = pref.last_detected_longitude
    if location_accuracy is None:
        location_accuracy = pref.last_detected_accuracy
    if not (full_address or '').strip() and not (formatted_address or '').strip():
        full_address = pref.last_detected_location_name or pref.saved_location_name
    if not (formatted_address or '').strip() and (full_address or '').strip():
        formatted_address = full_address

    if latitude is None or longitude is None:
        raise LocationPreferenceError(
            'latitude and longitude are required to save a place.',
            code='validation',
        )

    warning = accuracy_warning_code(location_accuracy)
    place = create_delivery_place(
        customer_profile,
        label=label,
        full_address=full_address or '',
        formatted_address=formatted_address or '',
        latitude=latitude,
        longitude=longitude,
        location_source=location_source or 'gps',
        location_accuracy=location_accuracy,
        city=city,
        area=area,
        building_name=building_name,
        floor=floor,
        flat_number=flat_number,
        landmark=landmark,
        is_verified_location=True,
    )

    now = timezone.now()
    if set_as_active:
        pref.active_delivery_place = place
        pref.saved_latitude = place.latitude
        pref.saved_longitude = place.longitude
        pref.saved_location_name = (
            (place.formatted_address or place.full_address or label)[:255]
        )
        pref.saved_at = now
        pref.is_active = True
        pref.save(
            update_fields=[
                'active_delivery_place',
                'saved_latitude',
                'saved_longitude',
                'saved_location_name',
                'saved_at',
                'is_active',
                'updated_at',
            ]
        )

    _apply_optional_meal_defaults(
        customer_profile,
        place,
        set_lunch_default=set_lunch_default,
        set_dinner_default=set_dinner_default,
        set_as_default_delivery_place=set_as_default_delivery_place,
    )
    return place, pref, warning


@transaction.atomic
def set_active_from_place(customer_profile, place_public_id) -> CustomerLocationPreference:
    place = get_place_or_error(customer_profile, place_public_id)
    pref = get_or_create_location_preference(customer_profile)
    pref.active_delivery_place = place
    pref.saved_latitude = place.latitude
    pref.saved_longitude = place.longitude
    pref.saved_location_name = (place.formatted_address or place.full_address or place.label)[:255]
    pref.saved_at = timezone.now()
    pref.is_active = True
    pref.save(
        update_fields=[
            'active_delivery_place',
            'saved_latitude',
            'saved_longitude',
            'saved_location_name',
            'saved_at',
            'is_active',
            'updated_at',
        ]
    )
    return pref


@transaction.atomic
def clear_location_preference(customer_profile) -> CustomerLocationPreference:
    pref = get_or_create_location_preference(customer_profile)
    pref.active_delivery_place = None
    pref.saved_latitude = None
    pref.saved_longitude = None
    pref.saved_location_name = ''
    pref.saved_at = None
    pref.is_active = False
    pref.save(
        update_fields=[
            'active_delivery_place',
            'saved_latitude',
            'saved_longitude',
            'saved_location_name',
            'saved_at',
            'is_active',
            'updated_at',
        ]
    )
    return pref


def get_guest_location_offer(guest_session_id: str) -> dict:
    session_id = (guest_session_id or '').strip()
    if not session_id:
        return {'exists': False}
    row = (
        ServiceAreaRequest.objects.filter(guest_session_id=session_id)
        .order_by('-requested_at')
        .first()
    )
    if row is None:
        return {'exists': False}
    return {
        'exists': True,
        'guest_session_id': session_id,
        'latitude': row.latitude,
        'longitude': row.longitude,
        'accuracy': row.accuracy,
        'location_name': row.detected_location_name or None,
        'formatted_address': row.formatted_address or None,
        'requested_at': row.requested_at,
        'is_serviceable': row.is_serviceable,
    }


@transaction.atomic
def accept_guest_location_offer(
    customer_profile,
    *,
    guest_session_id: str,
    label: str,
    full_address=None,
    formatted_address=None,
    set_lunch_default: bool = False,
    set_dinner_default: bool = False,
    set_as_default_delivery_place: bool = False,
) -> tuple[object, CustomerLocationPreference, str | None]:
    offer = get_guest_location_offer(guest_session_id)
    if not offer.get('exists'):
        raise LocationPreferenceError(
            'No guest location found for this session.',
            code='not_found',
        )
    address_text = (
        (full_address or '').strip()
        or (formatted_address or '').strip()
        or (offer.get('formatted_address') or '')
        or (offer.get('location_name') or '')
    )
    return save_detected_as_place(
        customer_profile,
        label=label,
        full_address=address_text,
        formatted_address=offer.get('formatted_address') or address_text,
        latitude=offer['latitude'],
        longitude=offer['longitude'],
        location_source='guest_migration',
        location_accuracy=offer.get('accuracy'),
        set_lunch_default=set_lunch_default,
        set_dinner_default=set_dinner_default,
        set_as_default_delivery_place=set_as_default_delivery_place,
        set_as_active=True,
    )


def saved_location_hint_for_check(customer_profile) -> dict:
    """Additive hint for service-area check responses."""
    if customer_profile is None:
        return {'exists': False}
    payload = get_location_preference_payload(customer_profile)
    if not payload.get('exists'):
        return {'exists': False}
    saved = payload.get('saved') or {}
    if not saved.get('exists'):
        return {'exists': False}
    return {
        'exists': True,
        'address_id': saved.get('address_id'),
        'stale': bool(payload.get('stale')),
    }


def get_location_settings():
    return CustomerLocationSettings.load()


def update_location_settings(
    *,
    duplicate_radius_km=None,
    max_active_delivery_places=None,
    location_refresh_interval_hours=None,
):
    settings_obj = CustomerLocationSettings.load()
    if duplicate_radius_km is not None:
        settings_obj.duplicate_radius_km = Decimal(str(duplicate_radius_km))
    if max_active_delivery_places is not None:
        settings_obj.max_active_delivery_places = int(max_active_delivery_places)
    if location_refresh_interval_hours is not None:
        settings_obj.location_refresh_interval_hours = int(location_refresh_interval_hours)
    settings_obj.save()
    return settings_obj
