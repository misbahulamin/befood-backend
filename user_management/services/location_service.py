"""Provider-agnostic location helpers for delivery places and preferences."""

from decimal import Decimal, InvalidOperation

from django.conf import settings

from service_area.services.geo import haversine_km, validate_coordinates

GEO_LOCATION_SOURCES = frozenset({'gps', 'map_pin', 'search', 'guest_migration'})
LOW_LOCATION_ACCURACY = 'LOW_LOCATION_ACCURACY'


class LocationServiceError(Exception):
    def __init__(self, message, code='location_error'):
        super().__init__(message)
        self.code = code


def calculate_distance(lat1, lng1, lat2, lng2) -> Decimal:
    return haversine_km(lat1, lng1, lat2, lng2)


def validate_location_coordinates(latitude, longitude) -> tuple[Decimal, Decimal]:
    try:
        return validate_coordinates(latitude, longitude)
    except ValueError as exc:
        raise LocationServiceError(str(exc), code='validation') from exc


def normalize_accuracy(accuracy) -> Decimal | None:
    if accuracy is None:
        return None
    try:
        value = Decimal(str(accuracy))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LocationServiceError('accuracy must be a number.', code='validation') from exc
    if value < 0:
        raise LocationServiceError('accuracy must be non-negative.', code='validation')
    return value


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


def accuracy_warning_code(accuracy) -> str | None:
    """Soft warning only; never blocks the operation."""
    if accuracy is None:
        return None
    if is_location_reliable(accuracy):
        return None
    return LOW_LOCATION_ACCURACY


def reverse_geocode(latitude, longitude) -> dict:
    """
    Pluggable reverse-geocode seam. v1 does not call external providers;
    clients supply location names. Future Google/OSM adapters plug in here.
    """
    validate_location_coordinates(latitude, longitude)
    return {
        'implemented': False,
        'provider': None,
        'formatted_address': None,
        'location_name': None,
        'detail': 'Client-supplied names are used; server reverse geocode is not configured.',
    }


def requires_coordinates(location_source: str | None) -> bool:
    return (location_source or '') in GEO_LOCATION_SOURCES


__all__ = [
    'GEO_LOCATION_SOURCES',
    'LOW_LOCATION_ACCURACY',
    'LocationServiceError',
    'accuracy_threshold_m',
    'accuracy_warning_code',
    'calculate_distance',
    'is_location_reliable',
    'normalize_accuracy',
    'requires_coordinates',
    'reverse_geocode',
    'validate_location_coordinates',
]
