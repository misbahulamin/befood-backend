from dataclasses import dataclass
from decimal import Decimal

from service_area.models import ServiceArea
from service_area.services.geo import haversine_km


@dataclass(frozen=True)
class MatchResult:
    service_available: bool
    distance_km: Decimal | None
    matched_area: ServiceArea | None
    nearest_area: ServiceArea | None


def match_service_areas(latitude, longitude) -> MatchResult:
    """
    Among active hubs, pick the nearest covering hub.
    If none cover, return nearest active hub with service_available=False.
    """
    hubs = list(ServiceArea.objects.filter(is_active=True))
    if not hubs:
        return MatchResult(
            service_available=False,
            distance_km=None,
            matched_area=None,
            nearest_area=None,
        )

    scored: list[tuple[Decimal, ServiceArea]] = []
    for hub in hubs:
        distance = haversine_km(latitude, longitude, hub.latitude, hub.longitude)
        scored.append((distance, hub))

    scored.sort(key=lambda item: item[0])
    nearest_distance, nearest_hub = scored[0]

    covering = [
        (distance, hub)
        for distance, hub in scored
        if distance <= hub.radius_km
    ]
    if covering:
        covering.sort(key=lambda item: item[0])
        distance, hub = covering[0]
        return MatchResult(
            service_available=True,
            distance_km=distance,
            matched_area=hub,
            nearest_area=nearest_hub,
        )

    return MatchResult(
        service_available=False,
        distance_km=nearest_distance,
        matched_area=None,
        nearest_area=nearest_hub,
    )
