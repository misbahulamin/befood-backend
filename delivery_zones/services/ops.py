from collections import defaultdict
from datetime import date

from django.db.models import Q

from delivery_zones.models import DeliveryLocation, DeliverySubLocation, DeliveryZone
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


def _has_sub_location_q() -> Q:
    return Q(subscription__customer__delivery_sub_location__isnull=False) | Q(
        order__customer__delivery_sub_location__isnull=False
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

    unassigned_count = base.exclude(_has_sub_location_q()).count()

    empty_counts = lambda: {
        'scheduled': 0,
        'delivered': 0,
        'skipped': 0,
        'missed': 0,
        'total': 0,
    }
    sub_counts: dict[int, dict[str, int]] = defaultdict(empty_counts)

    for row in base.filter(_has_sub_location_q()).values(
        'status',
        'subscription__customer__delivery_sub_location_id',
        'order__customer__delivery_sub_location_id',
    ):
        sub_id = (
            row['subscription__customer__delivery_sub_location_id']
            or row['order__customer__delivery_sub_location_id']
        )
        if not sub_id:
            continue
        status_key = row['status']
        sub_counts[sub_id]['total'] += 1
        if status_key in sub_counts[sub_id]:
            sub_counts[sub_id][status_key] += 1

    sub_locations = {
        sub.pk: sub
        for sub in DeliverySubLocation.objects.select_related(
            'location',
            'location__zone',
            'location__zone__assigned_delivery_man',
            'location__zone__assigned_delivery_man__user',
        ).filter(pk__in=sub_counts.keys())
    }

    zone_buckets: dict[int, dict] = {}
    location_buckets: dict[int, dict] = {}

    for sub_id, counts in sub_counts.items():
        sub = sub_locations.get(sub_id)
        if sub is None:
            continue
        loc = sub.location
        zone = loc.zone

        zone_bucket = zone_buckets.setdefault(
            zone.pk,
            {
                'zone': zone,
                'scheduled': 0,
                'delivered': 0,
                'skipped': 0,
                'missed': 0,
                'total': 0,
                'locations': [],
                '_loc_map': {},
            },
        )
        for key in ('scheduled', 'delivered', 'skipped', 'missed', 'total'):
            zone_bucket[key] += counts[key]

        loc_bucket = zone_bucket['_loc_map'].get(loc.pk)
        if loc_bucket is None:
            loc_bucket = {
                'public_id': str(loc.public_id),
                'name': loc.name,
                'priority': loc.priority,
                'status': loc.status,
                'counts': empty_counts(),
                'sub_locations': [],
            }
            zone_bucket['_loc_map'][loc.pk] = loc_bucket
            zone_bucket['locations'].append(loc_bucket)
            location_buckets[loc.pk] = loc_bucket

        for key in ('scheduled', 'delivered', 'skipped', 'missed', 'total'):
            loc_bucket['counts'][key] += counts[key]

        loc_bucket['sub_locations'].append(
            {
                'public_id': str(sub.public_id),
                'name': sub.name,
                'priority': sub.priority,
                'status': sub.status,
                'is_default': bool(sub.is_default),
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
                '_loc_map': {},
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
        for loc_entry in bucket['locations']:
            loc_entry['sub_locations'].sort(key=lambda x: (x['priority'], x['name']))
        bucket.pop('_loc_map', None)
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
        'unassigned_sub_location_count': unassigned_count,
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
