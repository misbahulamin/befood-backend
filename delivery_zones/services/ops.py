from collections import defaultdict
from datetime import date

from django.db.models import Q

from delivery_zones.models import DeliveryLocation, DeliveryZone
from delivery_zones.services.errors import DeliveryZoneError
from orders.models import OrderDelivery
from orders.services.subscription_parent import live_delivery_q


OPS_QUERY_ALLOWLIST = frozenset({'service_date', 'meal_period'})


def _parse_service_date(raw) -> date:
    if not raw:
        raise DeliveryZoneError('service_date is required (YYYY-MM-DD).', code='SERVICE_DATE_REQUIRED')
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise DeliveryZoneError(
            'service_date must be YYYY-MM-DD.',
            code='INVALID_SERVICE_DATE',
        ) from exc


def _has_location_q() -> Q:
    return Q(subscription__customer__delivery_location__isnull=False) | Q(
        order__customer__delivery_location__isnull=False
    )


def build_ops_summary(*, service_date: date, meal_period: str) -> dict:
    if meal_period not in OrderDelivery.MealPeriod.values:
        raise DeliveryZoneError(
            'meal_period must be lunch or dinner.',
            code='INVALID_MEAL_PERIOD',
        )

    base = OrderDelivery.objects.filter(
        live_delivery_q(service_date),
        service_date=service_date,
        meal_period=meal_period,
    )

    unassigned_count = base.exclude(_has_location_q()).count()

    loc_counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {'scheduled': 0, 'delivered': 0, 'skipped': 0, 'missed': 0, 'total': 0}
    )

    for row in base.filter(_has_location_q()).values(
        'status',
        'subscription__customer__delivery_location_id',
        'order__customer__delivery_location_id',
    ):
        loc_id = (
            row['subscription__customer__delivery_location_id']
            or row['order__customer__delivery_location_id']
        )
        if not loc_id:
            continue
        status_key = row['status']
        loc_counts[loc_id]['total'] += 1
        if status_key in loc_counts[loc_id]:
            loc_counts[loc_id][status_key] += 1

    locations = {
        loc.pk: loc
        for loc in DeliveryLocation.objects.select_related(
            'zone',
            'zone__assigned_delivery_man',
            'zone__assigned_delivery_man__user',
        ).filter(pk__in=loc_counts.keys())
    }

    zone_buckets: dict[int, dict] = {}
    for loc_id, counts in loc_counts.items():
        loc = locations.get(loc_id)
        if loc is None:
            continue
        zone = loc.zone
        bucket = zone_buckets.setdefault(
            zone.pk,
            {
                'zone': zone,
                'scheduled': 0,
                'delivered': 0,
                'skipped': 0,
                'missed': 0,
                'total': 0,
                'locations': [],
            },
        )
        for key in ('scheduled', 'delivered', 'skipped', 'missed', 'total'):
            bucket[key] += counts[key]
        bucket['locations'].append(
            {
                'public_id': str(loc.public_id),
                'name': loc.name,
                'priority': loc.priority,
                'status': loc.status,
                'counts': dict(counts),
            }
        )

    for zone in DeliveryZone.objects.select_related(
        'assigned_delivery_man', 'assigned_delivery_man__user'
    ).filter(status=DeliveryZone.Status.ACTIVE):
        zone_buckets.setdefault(
            zone.pk,
            {
                'zone': zone,
                'scheduled': 0,
                'delivered': 0,
                'skipped': 0,
                'missed': 0,
                'total': 0,
                'locations': [],
            },
        )

    zones_out = []
    workload = []
    for zone_id in sorted(
        zone_buckets.keys(),
        key=lambda zid: (zone_buckets[zid]['zone'].priority, zone_buckets[zid]['zone'].name),
    ):
        bucket = zone_buckets[zone_id]
        zone = bucket['zone']
        bucket['locations'].sort(key=lambda x: (x['priority'], x['name']))
        rider = zone.assigned_delivery_man
        counts = {
            'scheduled': bucket['scheduled'],
            'delivered': bucket['delivered'],
            'skipped': bucket['skipped'],
            'missed': bucket['missed'],
            'total': bucket['total'],
        }
        zones_out.append(
            {
                'public_id': str(zone.public_id),
                'name': zone.name,
                'code': zone.code,
                'priority': zone.priority,
                'status': zone.status,
                'assigned_delivery_man': (
                    {
                        'public_id': str(rider.public_id),
                        'email': rider.user.email,
                        'first_name': rider.user.first_name,
                        'last_name': rider.user.last_name,
                    }
                    if rider
                    else None
                ),
                'counts': counts,
                'locations': bucket['locations'],
            }
        )
        if rider:
            workload.append(
                {
                    'delivery_man_public_id': str(rider.public_id),
                    'email': rider.user.email,
                    'first_name': rider.user.first_name,
                    'last_name': rider.user.last_name,
                    'zone_public_id': str(zone.public_id),
                    'zone_name': zone.name,
                    'counts': counts,
                }
            )
        elif bucket['total'] > 0:
            workload.append(
                {
                    'delivery_man_public_id': None,
                    'email': None,
                    'first_name': None,
                    'last_name': None,
                    'zone_public_id': str(zone.public_id),
                    'zone_name': zone.name,
                    'unassigned_zone': True,
                    'counts': counts,
                }
            )

    return {
        'service_date': service_date.isoformat(),
        'meal_period': meal_period,
        'unassigned_location_count': unassigned_count,
        'zones': zones_out,
        'delivery_man_workload': workload,
    }


def parse_ops_query(params) -> tuple[date, str]:
    unknown = {k for k in params.keys() if k not in OPS_QUERY_ALLOWLIST}
    if unknown:
        raise DeliveryZoneError(
            f'Unsupported query parameter(s): {", ".join(sorted(unknown))}.',
            code='UNSUPPORTED_FILTER',
        )
    service_date = _parse_service_date(params.get('service_date'))
    meal_period = (params.get('meal_period') or '').strip()
    if not meal_period:
        raise DeliveryZoneError('meal_period is required.', code='MEAL_PERIOD_REQUIRED')
    return service_date, meal_period
