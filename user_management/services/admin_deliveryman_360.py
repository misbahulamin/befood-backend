"""Admin Delivery Man 360 analytics read helpers (no Request objects)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Avg, QuerySet, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from delivery_zones.services.board import zone_scoped_deliveries
from delivery_zones.services.zones import zone_for_rider
from orders.models import DeliveryActivityLog, DeliveryManDailySummary, OrderDelivery
from orders.services.meal_off import meal_off_business_now
from orders.services.subscription_parent import delivery_customer
from orders.services.wallet_balance_thresholds import customer_display_name
from user_management.models import RiderProfile

LIST_QUERY_ALLOWLIST = frozenset(
    {
        'q',
        'approval_status',
        'is_verified',
        'page',
        'page_size',
    }
)

DELIVERY_HISTORY_ALLOWLIST = frozenset(
    {
        'preset',
        'date_from',
        'date_to',
        'meal_period',
        'zone_public_id',
        'status',
        'logistics_status',
        'page',
        'page_size',
    }
)

TIMELINE_ALLOWLIST = frozenset({'date', 'page', 'page_size'})

ROUTE_ALLOWLIST = frozenset({'service_date', 'meal_period'})

RANKINGS_ALLOWLIST = frozenset(
    {
        'preset',
        'date_from',
        'date_to',
        'page',
        'page_size',
    }
)


def business_today() -> date:
    return meal_off_business_now().date()


def reject_unknown_params(query_params, allowlist: frozenset[str]) -> None:
    unknown = [key for key in query_params.keys() if key not in allowlist]
    if unknown:
        raise ValidationError(
            {
                'detail': f'Unsupported query parameter(s): {", ".join(sorted(unknown))}.',
                'error_code': 'UNSUPPORTED_FILTER',
            }
        )


def resolve_date_range(params: dict) -> tuple[date | None, date | None]:
    """Return (date_from, date_to) inclusive from preset or explicit dates."""
    preset = (params.get('preset') or '').strip().lower()
    today = business_today()
    if preset == 'today':
        return today, today
    if preset == 'yesterday':
        y = today - timedelta(days=1)
        return y, y
    if preset == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, today
    if preset == 'this_month':
        return today.replace(day=1), today
    date_from = params.get('date_from')
    date_to = params.get('date_to')
    parsed_from = parse_date(date_from) if isinstance(date_from, str) else date_from
    parsed_to = parse_date(date_to) if isinstance(date_to, str) else date_to
    if date_from and parsed_from is None:
        raise ValidationError({'date_from': ['Invalid date; use YYYY-MM-DD.']})
    if date_to and parsed_to is None:
        raise ValidationError({'date_to': ['Invalid date; use YYYY-MM-DD.']})
    return parsed_from, parsed_to


def rider_base_queryset() -> QuerySet[RiderProfile]:
    return RiderProfile.objects.select_related('user').prefetch_related(
        'assigned_delivery_zones'
    )


def get_rider_or_none(public_id) -> RiderProfile | None:
    try:
        return rider_base_queryset().get(public_id=public_id)
    except (RiderProfile.DoesNotExist, ValueError, TypeError):
        return None


def _zone_payload(rider: RiderProfile) -> dict | None:
    zone = zone_for_rider(rider)
    if zone is None:
        return None
    return {
        'public_id': str(zone.public_id),
        'name': zone.name,
        'code': zone.code,
        'priority': zone.priority,
        'status': zone.status,
    }


def _summary_totals(
    rider: RiderProfile, date_from: date, date_to: date
) -> dict[str, int]:
    agg = DeliveryManDailySummary.objects.filter(
        rider=rider, date__gte=date_from, date__lte=date_to
    ).aggregate(
        lunch=Sum('lunch_count'),
        dinner=Sum('dinner_count'),
        total=Sum('total_delivery'),
        completed=Sum('completed_count'),
        failed=Sum('failed_count'),
        avg_time=Avg('average_time_seconds'),
    )
    return {
        'lunch': int(agg['lunch'] or 0),
        'dinner': int(agg['dinner'] or 0),
        'total': int(agg['total'] or 0),
        'completed': int(agg['completed'] or 0),
        'failed': int(agg['failed'] or 0),
        'average_time_seconds': int(agg['avg_time']) if agg['avg_time'] is not None else None,
    }


def _lifetime_metrics(rider: RiderProfile) -> dict[str, Any]:
    delivered = OrderDelivery.objects.filter(
        delivered_by_rider=rider,
        status=OrderDelivery.DeliveryStatus.DELIVERED,
    )
    total = delivered.count()
    # Count distinct customers across order + subscription parents.
    sub_ids = set(
        delivered.exclude(subscription__customer_id=None).values_list(
            'subscription__customer_id', flat=True
        ).distinct()
    )
    order_ids = set(
        delivered.exclude(order__customer_id=None).values_list(
            'order__customer_id', flat=True
        ).distinct()
    )
    zones = delivered.exclude(logistics_zone_id=None).values('logistics_zone_id').distinct().count()
    return {
        'total': total,
        'customers_served': len(sub_ids | order_ids),
        'zones_covered': zones,
    }


def build_period_metrics(rider: RiderProfile) -> dict[str, Any]:
    today = business_today()
    month_start = today.replace(day=1)
    today_m = _summary_totals(rider, today, today)
    month_m = _summary_totals(rider, month_start, today)
    days_elapsed = max((today - month_start).days + 1, 1)
    lifetime = _lifetime_metrics(rider)
    return {
        'today': {
            'total': today_m['total'],
            'lunch': today_m['lunch'],
            'dinner': today_m['dinner'],
        },
        'month': {
            'year': today.year,
            'month': today.month,
            'label': today.strftime('%B %Y'),
            'total': month_m['total'],
            'lunch': month_m['lunch'],
            'dinner': month_m['dinner'],
            'average_per_day': round(month_m['total'] / days_elapsed, 1),
        },
        'lifetime': lifetime,
    }


def build_overview_payload(rider: RiderProfile) -> dict[str, Any]:
    metrics = build_period_metrics(rider)
    return {
        'public_id': str(rider.public_id),
        'name': f'{rider.user.first_name} {rider.user.last_name}'.strip() or rider.user.email,
        'email': rider.user.email,
        'phone': rider.phone,
        'assigned_zone': _zone_payload(rider),
        'joining_date': rider.created_at.date().isoformat() if rider.created_at else None,
        'status': rider.approval_status,
        'is_verified': rider.is_verified,
        'is_available': rider.is_available,
        'is_active': rider.user.is_active,
        'today': metrics['today'],
        'month': metrics['month'],
        'lifetime': metrics['lifetime'],
    }


def build_list_item(rider: RiderProfile) -> dict[str, Any]:
    metrics = build_period_metrics(rider)
    return {
        'public_id': str(rider.public_id),
        'name': f'{rider.user.first_name} {rider.user.last_name}'.strip() or rider.user.email,
        'phone': rider.phone,
        'email': rider.user.email,
        'assigned_zone': _zone_payload(rider),
        'is_available': rider.is_available,
        'is_verified': rider.is_verified,
        'approval_status': rider.approval_status,
        'joining_date': rider.created_at.date().isoformat() if rider.created_at else None,
        'today_delivery': metrics['today']['total'],
        'monthly_delivery': metrics['month']['total'],
        'lifetime_delivery': metrics['lifetime']['total'],
    }


def rider_deliveries_queryset(rider: RiderProfile, params: dict) -> QuerySet[OrderDelivery]:
    qs = (
        OrderDelivery.objects.filter(delivered_by_rider=rider)
        .select_related(
            'logistics_zone',
            'logistics_location',
            'delivered_by_rider__user',
            'order__customer__user',
            'subscription__customer__user',
        )
        .order_by('-service_date', '-delivered_at', '-marked_at', '-id')
    )
    date_from, date_to = resolve_date_range(params)
    if date_from:
        qs = qs.filter(service_date__gte=date_from)
    if date_to:
        qs = qs.filter(service_date__lte=date_to)
    meal_period = params.get('meal_period')
    if meal_period:
        qs = qs.filter(meal_period=meal_period)
    zone_public_id = params.get('zone_public_id')
    if zone_public_id:
        qs = qs.filter(logistics_zone__public_id=zone_public_id)
    status = params.get('status')
    if status:
        qs = qs.filter(status=status)
    logistics_status = params.get('logistics_status')
    if logistics_status:
        qs = qs.filter(logistics_status=logistics_status)
    return qs


def serialize_delivery_history_row(delivery: OrderDelivery) -> dict[str, Any]:
    customer = delivery_customer(delivery)
    user = customer.user if customer else None
    completed_at = delivery.delivered_at or delivery.marked_at
    return {
        'delivery_public_id': str(delivery.public_id),
        'service_date': delivery.service_date.isoformat(),
        'time': completed_at.isoformat() if completed_at else None,
        'customer_name': customer_display_name(customer) if customer else None,
        'customer_phone': getattr(customer, 'phone', None) if customer else None,
        'location': delivery.logistics_location.name if delivery.logistics_location_id else (
            delivery.delivery_label_snapshot or delivery.delivery_area_snapshot or None
        ),
        'zone': (
            {
                'public_id': str(delivery.logistics_zone.public_id),
                'name': delivery.logistics_zone.name,
                'code': delivery.logistics_zone.code,
            }
            if delivery.logistics_zone_id
            else None
        ),
        'meal_period': delivery.meal_period,
        'meal_status': delivery.status,
        'logistics_status': delivery.logistics_status or None,
        'delivered_by': (
            {
                'public_id': str(delivery.delivered_by_rider.public_id),
                'name': (
                    f'{delivery.delivered_by_rider.user.first_name} '
                    f'{delivery.delivered_by_rider.user.last_name}'
                ).strip()
                or delivery.delivered_by_rider.user.email,
            }
            if delivery.delivered_by_rider_id
            else None
        ),
        'delivery_duration_seconds': delivery.delivery_duration_seconds,
        'completion_latitude': (
            str(delivery.completion_latitude) if delivery.completion_latitude is not None else None
        ),
        'completion_longitude': (
            str(delivery.completion_longitude)
            if delivery.completion_longitude is not None
            else None
        ),
    }


def timeline_queryset(rider: RiderProfile, event_date: date) -> QuerySet[DeliveryActivityLog]:
    start = datetime.combine(event_date, datetime.min.time())
    end = datetime.combine(event_date, datetime.max.time())
    if timezone.is_naive(start):
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(start, tz)
        end = timezone.make_aware(end, tz)
    return (
        DeliveryActivityLog.objects.filter(rider=rider, timestamp__gte=start, timestamp__lte=end)
        .select_related('delivery')
        .order_by('timestamp', 'id')
    )


def serialize_timeline_event(log: DeliveryActivityLog) -> dict[str, Any]:
    return {
        'id': log.pk,
        'timestamp': log.timestamp.isoformat(),
        'status': log.status,
        'source': log.source,
        'note': log.note,
        'delivery_public_id': str(log.delivery.public_id) if log.delivery_id else None,
        'latitude': str(log.latitude) if log.latitude is not None else None,
        'longitude': str(log.longitude) if log.longitude is not None else None,
    }


def build_route_payload(
    rider: RiderProfile, *, service_date: date, meal_period: str
) -> dict[str, Any]:
    zone = zone_for_rider(rider)
    stops: list[dict[str, Any]] = []
    if zone is not None:
        qs = zone_scoped_deliveries(
            zone=zone,
            service_date=service_date,
            meal_period=meal_period,
            statuses=None,
            include_low_balance_blocked=True,
        )
        # Match board ordering: location priority then customer name.
        rows = list(qs)
        from delivery_zones.services.board import _delivery_location

        def sort_key(d: OrderDelivery):
            loc = _delivery_location(d)
            pri = loc.priority if loc is not None else 10**9
            cust = delivery_customer(d)
            name = customer_display_name(cust) if cust else ''
            return (pri, name.lower(), d.pk)

        rows.sort(key=sort_key)
        for idx, delivery in enumerate(rows, start=1):
            cust = delivery_customer(delivery)
            loc = _delivery_location(delivery)
            lat = delivery.delivery_latitude_snapshot
            lng = delivery.delivery_longitude_snapshot
            stops.append(
                {
                    'sequence': idx,
                    'delivery_public_id': str(delivery.public_id),
                    'customer_name': customer_display_name(cust) if cust else None,
                    'location_name': loc.name if loc else None,
                    'meal_status': delivery.status,
                    'logistics_status': delivery.logistics_status or None,
                    'latitude': str(lat) if lat is not None else None,
                    'longitude': str(lng) if lng is not None else None,
                }
            )
    return {
        'service_date': service_date.isoformat(),
        'meal_period': meal_period,
        'zone': _zone_payload(rider),
        'starting_point': {'label': 'Hub', 'sequence': 0},
        'stops': stops,
    }


def build_rankings(params: dict) -> list[dict[str, Any]]:
    date_from, date_to = resolve_date_range(params)
    today = business_today()
    if date_from is None and date_to is None:
        date_from = date_to = today
    elif date_from is None:
        date_from = date_to
    elif date_to is None:
        date_to = date_from

    rows = (
        DeliveryManDailySummary.objects.filter(date__gte=date_from, date__lte=date_to)
        .values('rider_id')
        .annotate(
            total_delivery=Sum('total_delivery'),
            completed_count=Sum('completed_count'),
            failed_count=Sum('failed_count'),
            average_time_seconds=Avg('average_time_seconds'),
        )
        .order_by('-total_delivery', 'rider_id')
    )
    rider_ids = [r['rider_id'] for r in rows]
    riders = {
        r.pk: r
        for r in RiderProfile.objects.filter(pk__in=rider_ids).select_related('user')
    }
    result = []
    for row in rows:
        rider = riders.get(row['rider_id'])
        if rider is None:
            continue
        completed = int(row['completed_count'] or 0)
        failed = int(row['failed_count'] or 0)
        denom = completed + failed
        completion_rate = round(completed / denom, 4) if denom else None
        avg = row['average_time_seconds']
        result.append(
            {
                'public_id': str(rider.public_id),
                'name': f'{rider.user.first_name} {rider.user.last_name}'.strip()
                or rider.user.email,
                'total_delivery': int(row['total_delivery'] or 0),
                'average_delivery_time_seconds': int(avg) if avg is not None else None,
                'completion_rate': completion_rate,
                'failed_delivery_count': failed,
            }
        )
    return result
