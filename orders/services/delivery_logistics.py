"""Rider logistics tracking for OrderDelivery stops (separate from meal status)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from orders.models import DeliveryActivityLog, DeliveryManDailySummary, OrderDelivery
from orders.services.subscription_parent import delivery_customer

# Phase B enforced path: sequential forward transitions.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    '': frozenset({'assigned', 'accepted', 'picked_up', 'out_for_delivery', 'delivered', 'failed'}),
    OrderDelivery.LogisticsStatus.ASSIGNED: frozenset(
        {'accepted', 'picked_up', 'out_for_delivery', 'delivered', 'failed', 'cancelled'}
    ),
    OrderDelivery.LogisticsStatus.ACCEPTED: frozenset(
        {'picked_up', 'out_for_delivery', 'delivered', 'failed', 'cancelled'}
    ),
    OrderDelivery.LogisticsStatus.PICKED_UP: frozenset(
        {'out_for_delivery', 'delivered', 'failed', 'cancelled'}
    ),
    OrderDelivery.LogisticsStatus.OUT_FOR_DELIVERY: frozenset(
        {'delivered', 'failed', 'cancelled'}
    ),
    OrderDelivery.LogisticsStatus.DELIVERED: frozenset(),
    OrderDelivery.LogisticsStatus.FAILED: frozenset(),
    OrderDelivery.LogisticsStatus.CANCELLED: frozenset(),
}

STATUS_TIMESTAMP_FIELD = {
    OrderDelivery.LogisticsStatus.ASSIGNED: 'assigned_at',
    OrderDelivery.LogisticsStatus.ACCEPTED: 'accepted_at',
    OrderDelivery.LogisticsStatus.PICKED_UP: 'picked_up_at',
    OrderDelivery.LogisticsStatus.OUT_FOR_DELIVERY: 'out_for_delivery_at',
    OrderDelivery.LogisticsStatus.DELIVERED: 'delivered_at',
    OrderDelivery.LogisticsStatus.FAILED: 'failed_at',
}


class LogisticsError(Exception):
    def __init__(self, message: str, code: str = 'LOGISTICS_ERROR'):
        super().__init__(message)
        self.code = code


def compute_delivery_duration_seconds(delivery: OrderDelivery) -> int | None:
    """Prefer picked_up → delivered, else out_for_delivery / assigned → delivered."""
    end = delivery.delivered_at
    if end is None:
        return None
    start = delivery.picked_up_at or delivery.out_for_delivery_at or delivery.assigned_at
    if start is None:
        return None
    delta = int((end - start).total_seconds())
    return delta if delta >= 0 else None


def append_activity_log(
    *,
    delivery: OrderDelivery,
    status: str,
    rider=None,
    timestamp: datetime | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    source: str = 'system',
    note: str = '',
) -> DeliveryActivityLog:
    return DeliveryActivityLog.objects.create(
        delivery=delivery,
        rider=rider,
        status=status,
        timestamp=timestamp or timezone.now(),
        latitude=latitude,
        longitude=longitude,
        source=source,
        note=note or '',
    )


def _resolve_zone_location(delivery: OrderDelivery):
    customer = delivery_customer(delivery)
    if customer is None:
        return None, None
    location = getattr(customer, 'delivery_location', None)
    if location is None:
        return None, None
    return getattr(location, 'zone', None), location


def record_phase_a_delivered(
    delivery: OrderDelivery,
    *,
    rider,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    source: str = 'deliveryman',
    note: str = '',
) -> OrderDelivery:
    """
    Phase A shortcut: set logistics delivered + attribution without requiring intermediates.

    Idempotent when already logistics-delivered for the same rider.
    """
    already_logistics_delivered = (
        delivery.logistics_status == OrderDelivery.LogisticsStatus.DELIVERED
    )
    now = timezone.now()
    update_fields = ['logistics_status', 'delivered_at', 'updated_at']

    if delivery.delivered_by_rider_id is None and rider is not None:
        delivery.delivered_by_rider = rider
        update_fields.append('delivered_by_rider')

    zone, location = _resolve_zone_location(delivery)
    if delivery.logistics_zone_id is None and zone is not None:
        delivery.logistics_zone = zone
        update_fields.append('logistics_zone')
    if delivery.logistics_location_id is None and location is not None:
        delivery.logistics_location = location
        update_fields.append('logistics_location')

    delivery.logistics_status = OrderDelivery.LogisticsStatus.DELIVERED
    if delivery.delivered_at is None:
        delivery.delivered_at = now

    if latitude is not None:
        delivery.completion_latitude = latitude
        update_fields.append('completion_latitude')
    if longitude is not None:
        delivery.completion_longitude = longitude
        update_fields.append('completion_longitude')

    duration = compute_delivery_duration_seconds(delivery)
    if duration is not None:
        delivery.delivery_duration_seconds = duration
        update_fields.append('delivery_duration_seconds')

    delivery.save(update_fields=list(dict.fromkeys(update_fields)))

    if not already_logistics_delivered:
        append_activity_log(
            delivery=delivery,
            status=OrderDelivery.LogisticsStatus.DELIVERED,
            rider=rider,
            timestamp=delivery.delivered_at or now,
            latitude=latitude,
            longitude=longitude,
            source=source,
            note=note,
        )
        if rider is not None:
            upsert_daily_summary_for_completed(delivery, rider=rider)

    return delivery


@transaction.atomic
def transition_logistics_status(
    delivery: OrderDelivery,
    to_status: str,
    *,
    rider=None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    source: str = 'deliveryman',
    note: str = '',
    allow_phase_a_deliver_shortcut: bool = False,
) -> OrderDelivery:
    """
    Apply a logistics status transition with timestamp + activity log.

    When ``allow_phase_a_deliver_shortcut`` and ``to_status=delivered``, intermediates
    may be skipped (mobile mark-delivered path).
    """
    if to_status not in OrderDelivery.LogisticsStatus.values:
        raise LogisticsError(f'Unknown logistics status: {to_status}', code='INVALID_STATUS')

    locked = (
        OrderDelivery.objects.select_for_update(of=('self',))
        .select_related(
            'order__customer__delivery_location__zone',
            'subscription__customer__delivery_location__zone',
            'delivered_by_rider',
        )
        .get(pk=delivery.pk)
    )
    current = locked.logistics_status or ''

    if current == to_status:
        return locked

    if to_status == OrderDelivery.LogisticsStatus.DELIVERED and allow_phase_a_deliver_shortcut:
        return record_phase_a_delivered(
            locked,
            rider=rider,
            latitude=latitude,
            longitude=longitude,
            source=source,
            note=note,
        )

    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if to_status not in allowed:
        raise LogisticsError(
            f'Cannot transition logistics from {current or "(empty)"} to {to_status}.',
            code='INVALID_TRANSITION',
        )

    now = timezone.now()
    locked.logistics_status = to_status
    update_fields = ['logistics_status', 'updated_at']

    ts_field = STATUS_TIMESTAMP_FIELD.get(to_status)
    if ts_field and getattr(locked, ts_field) is None:
        setattr(locked, ts_field, now)
        update_fields.append(ts_field)

    if rider is not None and locked.delivered_by_rider_id is None:
        # Bind rider early on first transition; keep immutable once set.
        locked.delivered_by_rider = rider
        update_fields.append('delivered_by_rider')

    zone, location = _resolve_zone_location(locked)
    if locked.logistics_zone_id is None and zone is not None:
        locked.logistics_zone = zone
        update_fields.append('logistics_zone')
    if locked.logistics_location_id is None and location is not None:
        locked.logistics_location = location
        update_fields.append('logistics_location')

    if to_status == OrderDelivery.LogisticsStatus.DELIVERED:
        if latitude is not None:
            locked.completion_latitude = latitude
            update_fields.append('completion_latitude')
        if longitude is not None:
            locked.completion_longitude = longitude
            update_fields.append('completion_longitude')
        duration = compute_delivery_duration_seconds(locked)
        if duration is not None:
            locked.delivery_duration_seconds = duration
            update_fields.append('delivery_duration_seconds')

    locked.save(update_fields=list(dict.fromkeys(update_fields)))

    append_activity_log(
        delivery=locked,
        status=to_status,
        rider=rider,
        timestamp=now,
        latitude=latitude,
        longitude=longitude,
        source=source,
        note=note,
    )

    if to_status == OrderDelivery.LogisticsStatus.DELIVERED and rider is not None:
        upsert_daily_summary_for_completed(locked, rider=rider)
    elif to_status == OrderDelivery.LogisticsStatus.FAILED and rider is not None:
        upsert_daily_summary_for_failed(locked, rider=rider)

    locked.refresh_from_db()
    return locked


def upsert_daily_summary_for_completed(delivery: OrderDelivery, *, rider) -> DeliveryManDailySummary:
    """Increment completed KPIs for the delivery's service_date (not skip)."""
    summary, _ = DeliveryManDailySummary.objects.select_for_update().get_or_create(
        rider=rider,
        date=delivery.service_date,
    )
    if delivery.meal_period == OrderDelivery.MealPeriod.LUNCH:
        summary.lunch_count += 1
    elif delivery.meal_period == OrderDelivery.MealPeriod.DINNER:
        summary.dinner_count += 1
    summary.total_delivery += 1
    summary.completed_count += 1
    _recompute_average_time(summary, rider=rider)
    summary.save()
    return summary


def upsert_daily_summary_for_failed(delivery: OrderDelivery, *, rider) -> DeliveryManDailySummary:
    summary, _ = DeliveryManDailySummary.objects.select_for_update().get_or_create(
        rider=rider,
        date=delivery.service_date,
    )
    summary.failed_count += 1
    summary.save(update_fields=['failed_count'])
    return summary


def _recompute_average_time(summary: DeliveryManDailySummary, *, rider) -> None:
    agg = OrderDelivery.objects.filter(
        delivered_by_rider=rider,
        service_date=summary.date,
        status=OrderDelivery.DeliveryStatus.DELIVERED,
        delivery_duration_seconds__isnull=False,
    ).aggregate(avg=Avg('delivery_duration_seconds'))
    avg = agg['avg']
    summary.average_time_seconds = int(avg) if avg is not None else None


def rebuild_daily_summaries(
    *,
    date_from: date,
    date_to: date,
) -> int:
    """
    Rebuild DeliveryManDailySummary rows from attributed delivered/failed stops.

    Returns number of summary rows written.
    """
    DeliveryManDailySummary.objects.filter(date__gte=date_from, date__lte=date_to).delete()

    delivered = (
        OrderDelivery.objects.filter(
            service_date__gte=date_from,
            service_date__lte=date_to,
            status=OrderDelivery.DeliveryStatus.DELIVERED,
            delivered_by_rider__isnull=False,
        )
        .values('delivered_by_rider_id', 'service_date')
        .annotate(
            lunch_count=Count('id', filter=Q(meal_period=OrderDelivery.MealPeriod.LUNCH)),
            dinner_count=Count('id', filter=Q(meal_period=OrderDelivery.MealPeriod.DINNER)),
            completed_count=Count('id'),
            avg_time=Avg('delivery_duration_seconds'),
        )
    )

    failed = (
        OrderDelivery.objects.filter(
            service_date__gte=date_from,
            service_date__lte=date_to,
            logistics_status=OrderDelivery.LogisticsStatus.FAILED,
            delivered_by_rider__isnull=False,
        )
        .values('delivered_by_rider_id', 'service_date')
        .annotate(failed_count=Count('id'))
    )
    failed_map = {
        (row['delivered_by_rider_id'], row['service_date']): row['failed_count'] for row in failed
    }

    created = 0
    for row in delivered:
        key = (row['delivered_by_rider_id'], row['service_date'])
        avg = row['avg_time']
        DeliveryManDailySummary.objects.create(
            rider_id=row['delivered_by_rider_id'],
            date=row['service_date'],
            lunch_count=row['lunch_count'],
            dinner_count=row['dinner_count'],
            total_delivery=row['completed_count'],
            completed_count=row['completed_count'],
            failed_count=failed_map.get(key, 0),
            average_time_seconds=int(avg) if avg is not None else None,
        )
        created += 1
        failed_map.pop(key, None)

    # Failed-only days with no completed deliveries
    for (rider_id, svc_date), failed_count in failed_map.items():
        DeliveryManDailySummary.objects.create(
            rider_id=rider_id,
            date=svc_date,
            failed_count=failed_count,
        )
        created += 1

    return created
