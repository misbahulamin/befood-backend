"""Rider-facing today delivery summary (counts + package breakdown)."""

from __future__ import annotations

from datetime import datetime

from django.db.models import CharField, Count, Value
from django.db.models.functions import Cast, Coalesce

from delivery_zones.services.board import zone_scoped_deliveries
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.zones import zone_for_rider
from orders.models import OrderDelivery
from orders.services.meal_off import get_current_delivery_period, get_meal_off_settings
from user_management.models import RiderProfile


def build_deliveryman_today_summary(
    rider: RiderProfile,
    *,
    now: datetime | None = None,
) -> dict:
    """
    Zone-scoped stop counts for the active meal window.

    Same scope as ``build_deliveryman_board``: assigned zone, meal-off business
    today + active period, low-balance blocked customers excluded.
    Primary metrics use OrderDelivery stop counts (not meal quantity).
    """
    settings_obj = get_meal_off_settings()
    service_date, active_meal_period = get_current_delivery_period(
        now,
        settings_obj=settings_obj,
    )
    timezone_name = settings_obj.timezone

    zone = zone_for_rider(rider)
    if zone is None:
        return {
            'service_date': service_date.isoformat(),
            'active_meal_period': active_meal_period,
            'timezone': timezone_name,
            'zone': None,
            'total': 0,
            'delivered': 0,
            'pending': 0,
            'packages': [],
            'message': 'No delivery zone assigned.',
        }

    zone_payload = {
        'public_id': str(zone.public_id),
        'name': zone.name,
        'code': zone.code,
        'priority': zone.priority,
    }

    if active_meal_period is None:
        return {
            'service_date': service_date.isoformat(),
            'active_meal_period': None,
            'timezone': timezone_name,
            'zone': zone_payload,
            'total': 0,
            'delivered': 0,
            'pending': 0,
            'packages': [],
            'message': 'No active meal delivery window yet.',
        }

    if active_meal_period not in OrderDelivery.MealPeriod.values:
        raise DeliveryZoneError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )

    qs = zone_scoped_deliveries(
        zone=zone,
        service_date=service_date,
        meal_period=active_meal_period,
        statuses=[
            OrderDelivery.DeliveryStatus.SCHEDULED,
            OrderDelivery.DeliveryStatus.DELIVERED,
        ],
        include_low_balance_blocked=False,
    )

    pending = qs.filter(status=OrderDelivery.DeliveryStatus.SCHEDULED).count()
    delivered = qs.filter(status=OrderDelivery.DeliveryStatus.DELIVERED).count()
    total = pending + delivered

    package_rows = (
        qs.annotate(
            package_name=Coalesce(
                'subscription__meal_name_snapshot',
                'order__meal_name_snapshot',
                Value('Unknown package'),
            ),
            package_public_id=Coalesce(
                Cast('subscription__meal__public_id', output_field=CharField()),
                Cast('order__meal__public_id', output_field=CharField()),
            ),
        )
        .values('package_name', 'package_public_id')
        .annotate(count=Count('id'))
        .order_by('-count', 'package_name')
    )

    packages = [
        {
            'package_public_id': row['package_public_id'] or None,
            'package_name': row['package_name'] or 'Unknown package',
            'count': row['count'],
        }
        for row in package_rows
    ]

    return {
        'service_date': service_date.isoformat(),
        'active_meal_period': active_meal_period,
        'timezone': timezone_name,
        'zone': zone_payload,
        'total': total,
        'delivered': delivered,
        'pending': pending,
        'packages': packages,
    }
