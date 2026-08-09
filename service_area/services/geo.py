from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0
_DISTANCE_QUANT = Decimal('0.0001')


def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    """Great-circle distance in kilometers between two WGS84 points."""
    phi1, phi2 = radians(float(lat1)), radians(float(lat2))
    d_phi = radians(float(lat2) - float(lat1))
    d_lambda = radians(float(lon2) - float(lon1))

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    c = 2 * asin(min(1.0, sqrt(a)))
    distance = EARTH_RADIUS_KM * c
    return Decimal(str(distance)).quantize(_DISTANCE_QUANT, rounding=ROUND_HALF_UP)


def validate_coordinates(latitude, longitude) -> tuple[Decimal, Decimal]:
    lat = Decimal(str(latitude))
    lng = Decimal(str(longitude))
    if lat < Decimal('-90') or lat > Decimal('90'):
        raise ValueError('latitude must be between -90 and 90')
    if lng < Decimal('-180') or lng > Decimal('180'):
        raise ValueError('longitude must be between -180 and 180')
    return lat, lng
