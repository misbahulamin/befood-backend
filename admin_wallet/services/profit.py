"""Realized meal profit from charged deliveries × published slot snapshots."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import OrderDelivery
from orders.services.subscription_parent import delivery_meal

_MONEY = Decimal('0.01')
_ZERO = Decimal('0.00')


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_MONEY)


def _charged_deliveries_qs(*, start: datetime | None = None, end: datetime | None = None):
    qs = OrderDelivery.objects.filter(
        payment_status=OrderDelivery.PaymentStatus.CHARGED,
        charged_amount__isnull=False,
    ).select_related(
        'order__meal',
        'subscription__meal',
    )
    if start is not None:
        qs = qs.filter(updated_at__gte=start)
    if end is not None:
        qs = qs.filter(updated_at__lte=end)
    return qs


def _profit_for_delivery(delivery: OrderDelivery) -> tuple[object | None, Decimal, Decimal]:
    """
    Return (meal, revenue, profit) for one charged delivery.

    Profit uses published slot ``profit_snapshot`` only (never live catalog recompute).
    Missing meal/slot/snapshot → profit ``0.00``.
    """
    meal = delivery_meal(delivery)
    revenue = _quantize(Decimal(delivery.charged_amount or 0))
    if meal is None:
        return None, revenue, _ZERO

    slot = resolve_published_slot_for_delivery(
        meal_id=meal.id,
        service_date=delivery.service_date,
        meal_period=delivery.meal_period,
    )
    if slot is None or slot.profit_snapshot is None:
        return meal, revenue, _ZERO
    return meal, revenue, _quantize(Decimal(slot.profit_snapshot))


def meal_profit_recognized(*, start: datetime | None = None, end: datetime | None = None) -> Decimal:
    """
    Sum published slot profit snapshots for charged meal deliveries.

    Period filter uses ``OrderDelivery.updated_at`` (same axis as meal revenue recognition).
    """
    total = _ZERO
    for delivery in _charged_deliveries_qs(start=start, end=end).iterator(chunk_size=500):
        _, _, profit = _profit_for_delivery(delivery)
        total += profit
    return _quantize(total)


def meal_profit_by_package(*, start: datetime | None = None, end: datetime | None = None) -> list[dict]:
    """
    Package-wise charged delivery aggregates for dashboard drill-down.

    Each row: package_public_id, package_name, charged_deliveries, revenue, profit.
    Ordered by profit descending, then package_name. Packages with no charged
    deliveries in scope are omitted.
    """
    buckets: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)
    revenues: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    profits: dict[str, Decimal] = defaultdict(lambda: _ZERO)

    for delivery in _charged_deliveries_qs(start=start, end=end).iterator(chunk_size=500):
        meal, revenue, profit = _profit_for_delivery(delivery)
        if meal is None:
            continue
        key = str(meal.public_id)
        if key not in buckets:
            buckets[key] = {
                'package_public_id': meal.public_id,
                'package_name': meal.meal_name or '',
            }
        counts[key] += 1
        revenues[key] += revenue
        profits[key] += profit

    rows = []
    for key, meta in buckets.items():
        rows.append(
            {
                'package_public_id': meta['package_public_id'],
                'package_name': meta['package_name'],
                'charged_deliveries': counts[key],
                'revenue': _quantize(revenues[key]),
                'profit': _quantize(profits[key]),
            }
        )
    rows.sort(key=lambda r: (-r['profit'], r['package_name'] or ''))
    return rows
