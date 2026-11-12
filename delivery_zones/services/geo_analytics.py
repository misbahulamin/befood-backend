"""Period geo analytics matrix: Zone → Location → Sub-location (admin web)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db.models import DateField, Q
from django.db.models.functions import Coalesce, TruncDate
from django.utils.dateparse import parse_date

from delivery_zones.models import DeliveryLocation, DeliverySubLocation, DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.customer_lifecycle import (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_AT_RISK,
    LIFECYCLE_NEVER_SUBSCRIBED,
    LIFECYCLE_UNSUBSCRIBED,
    LIFECYCLE_WON_BACK,
    annotate_lifecycle,
    business_calendar_today,
)
from orders.services.subscription_parent import live_delivery_q
from user_management.models import CustomerProfile

BUSINESS_TZ = ZoneInfo('Asia/Dhaka')

GEO_ANALYTICS_QUERY_ALLOWLIST = frozenset(
    {
        'from',
        'to',
        'meal_period',
        'zone_public_id',
        'location_public_id',
        'sub_location_public_id',
    }
)

CHURN_RANKING_MIN_ACTIVE_BASE = 5
RANKING_LIMIT = 10

LIFECYCLE_KEYS = (
    LIFECYCLE_ACTIVE,
    LIFECYCLE_AT_RISK,
    LIFECYCLE_UNSUBSCRIBED,
    LIFECYCLE_NEVER_SUBSCRIBED,
    LIFECYCLE_WON_BACK,
)


@dataclass(frozen=True)
class GeoAnalyticsQuery:
    start: date
    end: date
    meal_period: str | None
    zone_public_id: str | None
    location_public_id: str | None
    sub_location_public_id: str | None


def _empty_customers() -> dict[str, int]:
    return {
        'total': 0,
        LIFECYCLE_ACTIVE: 0,
        LIFECYCLE_AT_RISK: 0,
        LIFECYCLE_UNSUBSCRIBED: 0,
        LIFECYCLE_NEVER_SUBSCRIBED: 0,
        LIFECYCLE_WON_BACK: 0,
    }


def _empty_volume() -> dict[str, int]:
    return {
        'scheduled': 0,
        'delivered': 0,
        'skipped': 0,
        'missed': 0,
        'total': 0,
    }


def _empty_churn() -> dict[str, Any]:
    return {
        'churned_count': 0,
        'active_at_period_start': 0,
        'churn_rate_percent': 0.0,
    }


def _churn_rate(churned: int, active_base: int) -> float:
    if active_base <= 0:
        return 0.0
    return round((churned / active_base) * 100, 2)


def _parse_required_date(raw, field: str) -> date:
    if raw is None or str(raw).strip() == '':
        raise DeliveryZoneError(
            f'{field} is required (YYYY-MM-DD).',
            code='DATE_RANGE_REQUIRED',
        )
    parsed = parse_date(str(raw).strip())
    if parsed is None:
        raise DeliveryZoneError(
            f'{field} must be YYYY-MM-DD.',
            code='INVALID_DATE',
        )
    return parsed


def parse_geo_analytics_query(params) -> GeoAnalyticsQuery:
    unknown = {k for k in params.keys() if k not in GEO_ANALYTICS_QUERY_ALLOWLIST}
    if unknown:
        raise DeliveryZoneError(
            f'Unsupported query parameter(s): {", ".join(sorted(unknown))}.',
            code='UNSUPPORTED_FILTER',
        )

    start = _parse_required_date(params.get('from'), 'from')
    end = _parse_required_date(params.get('to'), 'to')
    if end < start:
        raise DeliveryZoneError(
            'to must be on or after from.',
            code='INVALID_DATE_RANGE',
        )
    if (end - start).days > 366:
        raise DeliveryZoneError(
            'Date range cannot exceed 366 days.',
            code='DATE_RANGE_TOO_LONG',
        )

    meal_period = (params.get('meal_period') or '').strip() or None
    if meal_period is not None and meal_period not in OrderDelivery.MealPeriod.values:
        raise DeliveryZoneError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )

    zone_public_id = (params.get('zone_public_id') or '').strip() or None
    location_public_id = (params.get('location_public_id') or '').strip() or None
    sub_location_public_id = (params.get('sub_location_public_id') or '').strip() or None

    for label, value in (
        ('zone_public_id', zone_public_id),
        ('location_public_id', location_public_id),
        ('sub_location_public_id', sub_location_public_id),
    ):
        if value is None:
            continue
        try:
            UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise DeliveryZoneError(
                f'{label} must be a valid UUID.',
                code='INVALID_PUBLIC_ID',
            ) from exc

    return GeoAnalyticsQuery(
        start=start,
        end=end,
        meal_period=meal_period,
        zone_public_id=zone_public_id,
        location_public_id=location_public_id,
        sub_location_public_id=sub_location_public_id,
    )


def _resolve_scope(query: GeoAnalyticsQuery) -> tuple[set[int] | None, set[int] | None, set[int] | None]:
    """Return optional allowed zone/location/sub pk sets. None means unrestricted at that level."""
    zone_ids: set[int] | None = None
    location_ids: set[int] | None = None
    sub_ids: set[int] | None = None

    if query.zone_public_id:
        zone = DeliveryZone.objects.filter(public_id=query.zone_public_id).first()
        if zone is None:
            raise DeliveryZoneError('Zone not found.', code='ZONE_NOT_FOUND')
        zone_ids = {zone.pk}

    if query.location_public_id:
        location = (
            DeliveryLocation.objects.select_related('zone')
            .filter(public_id=query.location_public_id)
            .first()
        )
        if location is None:
            raise DeliveryZoneError('Location not found.', code='LOCATION_NOT_FOUND')
        if zone_ids is not None and location.zone_id not in zone_ids:
            raise DeliveryZoneError('Location not found.', code='LOCATION_NOT_FOUND')
        location_ids = {location.pk}
        zone_ids = {location.zone_id}

    if query.sub_location_public_id:
        sub = (
            DeliverySubLocation.objects.select_related('location', 'location__zone')
            .filter(public_id=query.sub_location_public_id)
            .first()
        )
        if sub is None:
            raise DeliveryZoneError('Sub-location not found.', code='SUB_LOCATION_NOT_FOUND')
        if location_ids is not None and sub.location_id not in location_ids:
            raise DeliveryZoneError('Sub-location not found.', code='SUB_LOCATION_NOT_FOUND')
        if zone_ids is not None and sub.location.zone_id not in zone_ids:
            raise DeliveryZoneError('Sub-location not found.', code='SUB_LOCATION_NOT_FOUND')
        sub_ids = {sub.pk}
        location_ids = {sub.location_id}
        zone_ids = {sub.location.zone_id}

    return zone_ids, location_ids, sub_ids


def _rider_summary(zone: DeliveryZone) -> dict | None:
    rider = zone.assigned_delivery_man
    if rider is None:
        return None
    user = rider.user
    return {
        'public_id': str(rider.public_id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    }


def _active_at_period_start_customer_ids(start: date) -> set[int]:
    return set(
        CustomerSubscription.objects.filter(started_on__lte=start)
        .filter(
            Q(status=CustomerSubscription.Status.ACTIVE)
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__gte=start,
            )
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__isnull=True,
                cancelled_at__date__gte=start,
            )
        )
        .values_list('customer_id', flat=True)
        .distinct()
    )


def _churned_customer_ids_in_period(start: date, end: date) -> set[int]:
    return set(
        CustomerSubscription.objects.filter(status=CustomerSubscription.Status.CANCELLED)
        .annotate(
            churn_d=Coalesce(
                'cancel_effective_on',
                TruncDate('cancelled_at', tzinfo=BUSINESS_TZ),
                output_field=DateField(),
            )
        )
        .filter(churn_d__gte=start, churn_d__lte=end)
        .values_list('customer_id', flat=True)
        .distinct()
    )


def _resolve_delivery_sub_id(row: dict) -> int | None:
    return (
        row.get('logistics_sub_location_id')
        or row.get('subscription__customer__delivery_sub_location_id')
        or row.get('order__customer__delivery_sub_location_id')
    )


def _add_volume(target: dict[str, int], status_key: str) -> None:
    target['total'] += 1
    if status_key in target:
        target[status_key] += 1


def _merge_customers(dst: dict[str, int], src: dict[str, int]) -> None:
    for key in dst:
        dst[key] += src[key]


def _merge_volume(dst: dict[str, int], src: dict[str, int]) -> None:
    for key in dst:
        dst[key] += src[key]


def _node_ref(*, kind: str, public_id, name: str, extra: dict | None = None) -> dict:
    payload = {
        'kind': kind,
        'public_id': str(public_id),
        'name': name,
    }
    if extra:
        payload.update(extra)
    return payload


def build_geo_analytics_matrix(params) -> dict[str, Any]:
    query = parse_geo_analytics_query(params)
    zone_scope, location_scope, sub_scope = _resolve_scope(query)
    today = business_calendar_today()

    zones_qs = (
        DeliveryZone.objects.select_related(
            'assigned_delivery_man',
            'assigned_delivery_man__user',
        )
        .filter(status=DeliveryZone.Status.ACTIVE)
        .order_by('priority', 'name')
    )
    if zone_scope is not None:
        zones_qs = zones_qs.filter(pk__in=zone_scope)
    zones = list(zones_qs)
    zone_by_id = {z.pk: z for z in zones}

    locations_qs = (
        DeliveryLocation.objects.filter(zone_id__in=zone_by_id.keys())
        .order_by('priority', 'name')
    )
    if location_scope is not None:
        locations_qs = locations_qs.filter(pk__in=location_scope)
    locations = list(locations_qs)
    location_by_id = {loc.pk: loc for loc in locations}

    subs_qs = (
        DeliverySubLocation.objects.filter(location_id__in=location_by_id.keys())
        .order_by('priority', 'name')
    )
    if sub_scope is not None:
        subs_qs = subs_qs.filter(pk__in=sub_scope)
    sub_locations = list(subs_qs)
    sub_by_id = {s.pk: s for s in sub_locations}

    # --- Customer density (current assignment) ---
    customers_by_sub: dict[int, dict[str, int]] = {
        sid: _empty_customers() for sid in sub_by_id
    }
    unassigned_customers = _empty_customers()

    customer_rows = annotate_lifecycle(
        CustomerProfile.objects.all(),
        today=today,
    ).values(
        'pk',
        'lifecycle',
        'delivery_sub_location_id',
    )
    customer_geo: dict[int, int | None] = {}
    for row in customer_rows:
        cid = row['pk']
        sub_id = row['delivery_sub_location_id']
        lifecycle = row['lifecycle'] or LIFECYCLE_NEVER_SUBSCRIBED
        customer_geo[cid] = sub_id
        if sub_id is None:
            bucket = unassigned_customers
        elif sub_id not in customers_by_sub:
            continue
        else:
            bucket = customers_by_sub[sub_id]
        bucket['total'] += 1
        if lifecycle in bucket:
            bucket[lifecycle] += 1

    # --- Churn ---
    active_at_start = _active_at_period_start_customer_ids(query.start)
    churned_ids = _churned_customer_ids_in_period(query.start, query.end)

    churn_by_sub: dict[int, dict[str, Any]] = {
        sid: _empty_churn() for sid in sub_by_id
    }
    unassigned_churn = _empty_churn()

    def _attr_churn_bucket(sub_id: int | None) -> dict[str, Any] | None:
        if sub_id is None:
            return unassigned_churn
        return churn_by_sub.get(sub_id)

    for cid in churned_ids:
        sub_id = customer_geo.get(cid)
        if cid not in customer_geo:
            # customer deleted edge-case — skip
            continue
        bucket = _attr_churn_bucket(sub_id)
        if bucket is None:
            continue
        bucket['churned_count'] += 1

    for cid in active_at_start:
        sub_id = customer_geo.get(cid)
        if cid not in customer_geo:
            continue
        bucket = _attr_churn_bucket(sub_id)
        if bucket is None:
            continue
        bucket['active_at_period_start'] += 1

    for bucket in list(churn_by_sub.values()) + [unassigned_churn]:
        bucket['churn_rate_percent'] = _churn_rate(
            bucket['churned_count'],
            bucket['active_at_period_start'],
        )

    # --- Meal volume ---
    volume_by_sub: dict[int, dict[str, int]] = {
        sid: _empty_volume() for sid in sub_by_id
    }
    unassigned_volume = _empty_volume()

    deliveries = OrderDelivery.objects.filter(
        live_delivery_q(),
        service_date__gte=query.start,
        service_date__lte=query.end,
    )
    if query.meal_period:
        deliveries = deliveries.filter(meal_period=query.meal_period)

    for row in deliveries.values(
        'status',
        'logistics_sub_location_id',
        'subscription__customer__delivery_sub_location_id',
        'order__customer__delivery_sub_location_id',
    ):
        sub_id = _resolve_delivery_sub_id(row)
        status_key = row['status']
        if sub_id is None:
            _add_volume(unassigned_volume, status_key)
            continue
        if sub_id not in volume_by_sub:
            continue
        _add_volume(volume_by_sub[sub_id], status_key)

    # --- Assemble hierarchy ---
    # Pre-aggregate location/zone from subs
    customers_by_loc: dict[int, dict[str, int]] = defaultdict(_empty_customers)
    churn_by_loc: dict[int, dict[str, Any]] = defaultdict(_empty_churn)
    volume_by_loc: dict[int, dict[str, int]] = defaultdict(_empty_volume)
    customers_by_zone: dict[int, dict[str, int]] = defaultdict(_empty_customers)
    churn_by_zone: dict[int, dict[str, Any]] = defaultdict(_empty_churn)
    volume_by_zone: dict[int, dict[str, int]] = defaultdict(_empty_volume)

    for sub in sub_locations:
        loc_id = sub.location_id
        zone_id = location_by_id[loc_id].zone_id
        _merge_customers(customers_by_loc[loc_id], customers_by_sub[sub.pk])
        _merge_volume(volume_by_loc[loc_id], volume_by_sub[sub.pk])
        loc_churn = churn_by_loc[loc_id]
        sub_churn = churn_by_sub[sub.pk]
        loc_churn['churned_count'] += sub_churn['churned_count']
        loc_churn['active_at_period_start'] += sub_churn['active_at_period_start']

        _merge_customers(customers_by_zone[zone_id], customers_by_sub[sub.pk])
        _merge_volume(volume_by_zone[zone_id], volume_by_sub[sub.pk])
        zone_churn = churn_by_zone[zone_id]
        zone_churn['churned_count'] += sub_churn['churned_count']
        zone_churn['active_at_period_start'] += sub_churn['active_at_period_start']

    for loc_id, bucket in churn_by_loc.items():
        bucket['churn_rate_percent'] = _churn_rate(
            bucket['churned_count'],
            bucket['active_at_period_start'],
        )
    for zone_id, bucket in churn_by_zone.items():
        bucket['churn_rate_percent'] = _churn_rate(
            bucket['churned_count'],
            bucket['active_at_period_start'],
        )

    locs_by_zone: dict[int, list[DeliveryLocation]] = defaultdict(list)
    for loc in locations:
        locs_by_zone[loc.zone_id].append(loc)

    subs_by_loc: dict[int, list[DeliverySubLocation]] = defaultdict(list)
    for sub in sub_locations:
        subs_by_loc[sub.location_id].append(sub)

    zones_out = []
    location_rank_nodes = []
    for zone in zones:
        loc_entries = []
        for loc in locs_by_zone.get(zone.pk, []):
            sub_entries = []
            for sub in subs_by_loc.get(loc.pk, []):
                sub_customers = customers_by_sub[sub.pk]
                sub_churn = churn_by_sub[sub.pk]
                sub_volume = volume_by_sub[sub.pk]
                sub_entries.append(
                    {
                        'public_id': str(sub.public_id),
                        'name': sub.name,
                        'priority': sub.priority,
                        'status': sub.status,
                        'is_default': bool(sub.is_default),
                        'customers': dict(sub_customers),
                        'churn': dict(sub_churn),
                        'volume': dict(sub_volume),
                    }
                )
            loc_customers = customers_by_loc.get(loc.pk, _empty_customers())
            loc_churn = churn_by_loc.get(loc.pk, _empty_churn())
            loc_volume = volume_by_loc.get(loc.pk, _empty_volume())
            loc_entry = {
                'public_id': str(loc.public_id),
                'name': loc.name,
                'priority': loc.priority,
                'status': loc.status,
                'customers': dict(loc_customers),
                'churn': dict(loc_churn),
                'volume': dict(loc_volume),
                'sub_locations': sub_entries,
            }
            loc_entries.append(loc_entry)
            location_rank_nodes.append(
                {
                    'ref': _node_ref(
                        kind='location',
                        public_id=loc.public_id,
                        name=loc.name,
                        extra={
                            'zone_public_id': str(zone.public_id),
                            'zone_name': zone.name,
                        },
                    ),
                    'customers_total': loc_customers['total'],
                    'churn_rate_percent': loc_churn['churn_rate_percent'],
                    'active_at_period_start': loc_churn['active_at_period_start'],
                    'delivered': loc_volume['delivered'],
                    'volume_total': loc_volume['total'],
                }
            )

        zone_customers = customers_by_zone.get(zone.pk, _empty_customers())
        zone_churn = churn_by_zone.get(zone.pk, _empty_churn())
        zone_volume = volume_by_zone.get(zone.pk, _empty_volume())
        rider = _rider_summary(zone)
        zones_out.append(
            {
                'public_id': str(zone.public_id),
                'name': zone.name,
                'code': zone.code,
                'priority': zone.priority,
                'status': zone.status,
                'assigned_delivery_man': rider,
                'customers': dict(zone_customers),
                'churn': dict(zone_churn),
                'volume': dict(zone_volume),
                'workload': {
                    'delivered': zone_volume['delivered'],
                    'total': zone_volume['total'],
                    'unassigned_zone': rider is None,
                },
                'locations': loc_entries,
            }
        )

    def _top(nodes, key, *, reverse=True, predicate=None, limit=RANKING_LIMIT):
        filtered = [n for n in nodes if predicate(n)] if predicate else list(nodes)
        filtered.sort(key=lambda n: (n[key], n['ref']['name']), reverse=reverse)
        return [
            {
                **n['ref'],
                'value': n[key],
                'customers_total': n['customers_total'],
                'churn_rate_percent': n['churn_rate_percent'],
                'active_at_period_start': n['active_at_period_start'],
                'delivered': n['delivered'],
                'volume_total': n['volume_total'],
            }
            for n in filtered[:limit]
        ]

    rankings = {
        'churn_min_active_base': CHURN_RANKING_MIN_ACTIVE_BASE,
        'highest_customer_density': _top(
            location_rank_nodes, 'customers_total', reverse=True
        ),
        'lowest_customer_density': _top(
            location_rank_nodes, 'customers_total', reverse=False
        ),
        'highest_churn_rate': _top(
            location_rank_nodes,
            'churn_rate_percent',
            reverse=True,
            predicate=lambda n: n['active_at_period_start']
            >= CHURN_RANKING_MIN_ACTIVE_BASE,
        ),
        'highest_meal_volume': _top(
            location_rank_nodes, 'delivered', reverse=True
        ),
        'unassigned': {
            'customers': dict(unassigned_customers),
            'churn': dict(unassigned_churn),
            'volume': dict(unassigned_volume),
        },
    }

    return {
        'from': query.start.isoformat(),
        'to': query.end.isoformat(),
        'meal_period': query.meal_period,
        'timezone': 'Asia/Dhaka',
        'attribution': {
            'customers_and_churn': 'current_assignment',
            'volume': 'logistics_sub_location_then_customer_sub_location',
        },
        'unassigned_customers': dict(unassigned_customers),
        'unassigned_volume': dict(unassigned_volume),
        'zones': zones_out,
        'rankings': rankings,
    }
