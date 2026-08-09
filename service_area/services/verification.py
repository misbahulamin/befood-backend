from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from meals.services.pricing import periods_for_meal_period
from service_area.models import ServiceAreaRequest
from service_area.services.geo import validate_coordinates
from service_area.services.matching import MatchResult, match_service_areas
from user_management.models import MealDeliveryDayOverride, MealDeliveryPreference
from user_management.services.delivery_preference import (
    _fallback_place,
    resolve_delivery_address,
    today_in_meal_tz,
)

LOW_LOCATION_ACCURACY = 'LOW_LOCATION_ACCURACY'
SERVICE_AREA_UNAVAILABLE = 'SERVICE_AREA_UNAVAILABLE'
DELIVERY_LOCATION_REQUIRED = 'DELIVERY_LOCATION_REQUIRED'


class ServiceAreaError(Exception):
    def __init__(self, message: str, code: str = 'SERVICE_AREA_ERROR'):
        super().__init__(message)
        self.code = code


def accuracy_threshold_m() -> Decimal:
    return Decimal(str(getattr(settings, 'SERVICE_AREA_ACCURACY_THRESHOLD_M', 500)))


def is_location_reliable(accuracy) -> bool:
    if accuracy is None:
        return True
    try:
        value = Decimal(str(accuracy))
    except (InvalidOperation, TypeError, ValueError):
        return True
    return value <= accuracy_threshold_m()


def _hub_payload(hub) -> dict | None:
    if hub is None:
        return None
    return {
        'public_id': str(hub.public_id),
        'name': hub.name,
        'latitude': hub.latitude,
        'longitude': hub.longitude,
        'radius_km': hub.radius_km,
    }


def _build_response(
    *,
    latitude: Decimal,
    longitude: Decimal,
    accuracy,
    location_name: str | None,
    match: MatchResult,
    location_reliable: bool,
) -> dict:
    warning_code = None if location_reliable else LOW_LOCATION_ACCURACY
    payload = {
        'verified': True,
        'service_available': match.service_available,
        'location_reliable': location_reliable,
        'warning_code': warning_code,
        'customer_location': {
            'latitude': latitude,
            'longitude': longitude,
            'accuracy': accuracy,
            'location_name': location_name or None,
        },
        'distance_km': match.distance_km,
        'matched_service_area': None,
        'nearest_service_area': None,
    }
    if match.service_available:
        payload['matched_service_area'] = _hub_payload(match.matched_area)
    else:
        payload['nearest_service_area'] = _hub_payload(match.nearest_area)
    return payload


@transaction.atomic
def check_service_area(
    *,
    latitude,
    longitude,
    accuracy=None,
    location_name: str | None = None,
    formatted_address: str | None = None,
    guest_session_id: str = '',
    customer_profile=None,
    request_kind: str = ServiceAreaRequest.RequestKind.CHECK,
) -> dict:
    """
    Verify coverage from device/browser coordinates only (never IP).
    Always persists a ServiceAreaRequest history row.
    """
    lat, lng = validate_coordinates(latitude, longitude)
    if accuracy is not None:
        try:
            accuracy = Decimal(str(accuracy))
            if accuracy < 0:
                raise ServiceAreaError('accuracy must be non-negative.', code='INVALID_ACCURACY')
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceAreaError('accuracy must be a number.', code='INVALID_ACCURACY') from exc

    match = match_service_areas(lat, lng)
    reliable = is_location_reliable(accuracy)
    hub = match.matched_area if match.service_available else match.nearest_area

    ServiceAreaRequest.objects.create(
        customer_profile=customer_profile,
        guest_session_id=(guest_session_id or '')[:64],
        latitude=lat,
        longitude=lng,
        accuracy=accuracy,
        detected_location_name=(location_name or '')[:255],
        formatted_address=(formatted_address or '')[:512],
        matched_service_area=hub,
        distance_km=match.distance_km,
        is_serviceable=match.service_available,
        request_kind=request_kind,
    )

    return _build_response(
        latitude=lat,
        longitude=lng,
        accuracy=accuracy,
        location_name=location_name,
        match=match,
        location_reliable=reliable,
    )


def record_demand(
    *,
    latitude,
    longitude,
    accuracy=None,
    location_name: str | None = None,
    formatted_address: str | None = None,
    guest_session_id: str = '',
    customer_profile=None,
) -> dict:
    """Persist demand CTA; does not grant serviceability."""
    return check_service_area(
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        location_name=location_name,
        formatted_address=formatted_address,
        guest_session_id=guest_session_id,
        customer_profile=customer_profile,
        request_kind=ServiceAreaRequest.RequestKind.DEMAND,
    )


def assert_serviceable(latitude, longitude) -> MatchResult:
    """Raise if coordinates are missing/invalid or outside all active hubs."""
    if latitude is None or longitude is None:
        raise ServiceAreaError(
            'Delivery location coordinates are required.',
            code=DELIVERY_LOCATION_REQUIRED,
        )
    try:
        lat, lng = validate_coordinates(latitude, longitude)
    except ValueError as exc:
        raise ServiceAreaError(str(exc), code=DELIVERY_LOCATION_REQUIRED) from exc

    match = match_service_areas(lat, lng)
    if not match.service_available:
        raise ServiceAreaError(
            'BeFood service is not available at this delivery location.',
            code=SERVICE_AREA_UNAVAILABLE,
        )
    return match


def _collect_places_for_meal(customer, meal_period: str):
    periods = periods_for_meal_period(meal_period)
    places = {}
    pref = MealDeliveryPreference.objects.filter(customer_profile=customer).select_related(
        'lunch_place',
        'dinner_place',
    ).first()
    for period in periods:
        if pref is not None:
            default = pref.lunch_place if period == 'lunch' else pref.dinner_place
            if default is not None and default.is_active:
                places[default.id] = default
        overrides = (
            MealDeliveryDayOverride.objects.filter(
                customer_profile=customer,
                meal_period=period,
                place__is_active=True,
            )
            .select_related('place')
        )
        for override in overrides:
            places[override.place_id] = override.place

    if not places:
        today = today_in_meal_tz()
        for period in periods:
            resolved = resolve_delivery_address(customer, today, period)
            if resolved is not None:
                places[resolved.id] = resolved
        if not places:
            fallback = _fallback_place(customer)
            if fallback is not None:
                places[fallback.id] = fallback
    return list(places.values())


def assert_customer_order_serviceable(customer, meal_period: str = 'both') -> None:
    """Checkout gate: every place used for the meal periods must be covered."""
    if not getattr(settings, 'SERVICE_AREA_ORDER_GATE_ENABLED', True):
        return

    places = _collect_places_for_meal(customer, meal_period)
    if not places:
        raise ServiceAreaError(
            'Add a delivery location with map coordinates before ordering.',
            code=DELIVERY_LOCATION_REQUIRED,
        )

    for place in places:
        assert_serviceable(place.latitude, place.longitude)
