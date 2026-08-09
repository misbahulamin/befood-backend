from decimal import Decimal, InvalidOperation

from django.db import transaction

from service_area.models import ServiceArea
from service_area.services.geo import validate_coordinates


class ServiceAreaManagementError(Exception):
    def __init__(self, message: str, code: str = 'SERVICE_AREA_MANAGEMENT_ERROR'):
        super().__init__(message)
        self.code = code


def _parse_radius(radius_km) -> Decimal:
    try:
        value = Decimal(str(radius_km))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ServiceAreaManagementError(
            'radius_km must be a positive number.',
            code='INVALID_RADIUS',
        ) from exc
    if value <= 0:
        raise ServiceAreaManagementError(
            'radius_km must be greater than zero.',
            code='INVALID_RADIUS',
        )
    return value


@transaction.atomic
def create_service_area(
    *,
    name: str,
    latitude,
    longitude,
    radius_km,
    description: str = '',
    is_active: bool = True,
    created_by=None,
) -> ServiceArea:
    name = (name or '').strip()
    if not name:
        raise ServiceAreaManagementError('name is required.', code='NAME_REQUIRED')
    try:
        lat, lng = validate_coordinates(latitude, longitude)
    except ValueError as exc:
        raise ServiceAreaManagementError(str(exc), code='INVALID_COORDINATES') from exc
    radius = _parse_radius(radius_km)
    return ServiceArea.objects.create(
        name=name,
        latitude=lat,
        longitude=lng,
        radius_km=radius,
        description=description or '',
        is_active=is_active,
        created_by=created_by,
    )


@transaction.atomic
def update_service_area(area: ServiceArea, **fields) -> ServiceArea:
    if 'name' in fields:
        name = (fields['name'] or '').strip()
        if not name:
            raise ServiceAreaManagementError('name is required.', code='NAME_REQUIRED')
        area.name = name
    if 'latitude' in fields or 'longitude' in fields:
        lat = fields.get('latitude', area.latitude)
        lng = fields.get('longitude', area.longitude)
        try:
            area.latitude, area.longitude = validate_coordinates(lat, lng)
        except ValueError as exc:
            raise ServiceAreaManagementError(str(exc), code='INVALID_COORDINATES') from exc
    if 'radius_km' in fields:
        area.radius_km = _parse_radius(fields['radius_km'])
    if 'description' in fields:
        area.description = fields['description'] or ''
    if 'is_active' in fields and fields['is_active'] is not None:
        area.is_active = bool(fields['is_active'])
    area.save()
    return area


@transaction.atomic
def set_service_area_active(area: ServiceArea, is_active: bool) -> ServiceArea:
    area.is_active = bool(is_active)
    area.save(update_fields=['is_active', 'updated_at'])
    return area


@transaction.atomic
def soft_delete_service_area(area: ServiceArea) -> ServiceArea:
    """Soft-delete: deactivate so history FKs remain intact."""
    return set_service_area_active(area, False)
