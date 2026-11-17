"""Rider-facing today delivery summary (counts + package breakdown)."""

from __future__ import annotations

from datetime import datetime

from django.db.models import CharField, Count, Value
from django.db.models.functions import Cast, Coalesce

from delivery_zones.services.board import _meal_quantity, zone_scoped_deliveries
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.zones import zone_for_rider
from orders.models import OrderDelivery
from orders.services.meal_off import get_current_delivery_period, get_meal_off_settings
from user_management.models import RiderProfile


def _empty_box_metrics() -> dict:
    return {
        'regular_meal_quantity': 0,
        'guest_meal_quantity': 0,
        'test_meal_quantity': 0,
        'total_meal_quantity': 0,
        'delivered_meal_quantity': 0,
        'pending_meal_quantity': 0,
    }


def _box_metrics_for_deliveries(deliveries: list[OrderDelivery]) -> dict:
    from orders.services.guest_meal import guest_quantities_by_delivery_ids
    from orders.services.test_meal import test_meal_quantities_by_delivery_ids

    guest_by_delivery = guest_quantities_by_delivery_ids([d.pk for d in deliveries])
    test_by_delivery = test_meal_quantities_by_delivery_ids([d.pk for d in deliveries])
    regular = 0
    guest = 0
    test = 0
    delivered_boxes = 0
    pending_boxes = 0
    for delivery in deliveries:
        meal_qty = _meal_quantity(delivery)
        guest_qty = int(guest_by_delivery.get(delivery.pk, 0))
        test_qty = int(test_by_delivery.get(delivery.pk, 0))
        if delivery.test_meal_order_id and test_qty <= 0:
            test_qty = 1
        row_total = meal_qty + guest_qty + test_qty
        regular += meal_qty
        guest += guest_qty
        test += test_qty
        if delivery.status == OrderDelivery.DeliveryStatus.DELIVERED:
            delivered_boxes += row_total
        else:
            pending_boxes += row_total
    return {
        'regular_meal_quantity': regular,
        'guest_meal_quantity': guest,
        'test_meal_quantity': test,
        'total_meal_quantity': regular + guest + test,
        'delivered_meal_quantity': delivered_boxes,
        'pending_meal_quantity': pending_boxes,
    }


def build_deliveryman_today_summary(
    rider: RiderProfile,
    *,
    now: datetime | None = None,
) -> dict:
    """
    Zone-scoped stop counts for the active meal window.

    Same scope as ``build_deliveryman_board``: assigned zone, meal-off business
    today + active period, low-balance blocked customers excluded.
    Existing ``total`` / ``delivered`` / ``pending`` remain stop counts.
    Additive ``*_meal_quantity`` fields are meal-box counts (regular + guest).
    """
    settings_obj = get_meal_off_settings()
    service_date, active_meal_period = get_current_delivery_period(
        now,
        settings_obj=settings_obj,
    )
    timezone_name = settings_obj.timezone
    empty_boxes = _empty_box_metrics()

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
            **empty_boxes,
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
            **empty_boxes,
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

    deliveries = list(qs)
    pending = sum(
        1
        for d in deliveries
        if d.status == OrderDelivery.DeliveryStatus.SCHEDULED
    )
    delivered = sum(
        1
        for d in deliveries
        if d.status == OrderDelivery.DeliveryStatus.DELIVERED
    )
    total = pending + delivered
    box_metrics = _box_metrics_for_deliveries(deliveries)

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
        **box_metrics,
    }
