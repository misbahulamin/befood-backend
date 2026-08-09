from datetime import datetime
from decimal import Decimal

from django.db.models import Avg, Count, Q, QuerySet
from django.utils.dateparse import parse_date, parse_datetime

from service_area.models import ServiceArea, ServiceAreaRequest

ALLOWED_REQUEST_FILTERS = frozenset(
    {
        'from',
        'to',
        'is_serviceable',
        'request_kind',
        'q',
        'page',
        'page_size',
    }
)


class ServiceAreaQueryError(Exception):
    def __init__(self, message: str, code: str = 'UNSUPPORTED_FILTER'):
        super().__init__(message)
        self.code = code


def _parse_bound(value: str, *, end: bool = False):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is not None:
        return dt
    day = parse_date(value)
    if day is None:
        raise ServiceAreaQueryError(
            f'Invalid date value: {value}',
            code='UNSUPPORTED_FILTER',
        )
    if end:
        return datetime.combine(day, datetime.max.time())
    return datetime.combine(day, datetime.min.time())


def reject_unknown_filters(query_params) -> None:
    unknown = [key for key in query_params.keys() if key not in ALLOWED_REQUEST_FILTERS]
    if unknown:
        raise ServiceAreaQueryError(
            f'Unsupported filter(s): {", ".join(sorted(unknown))}',
            code='UNSUPPORTED_FILTER',
        )


def filter_service_areas(query_params) -> QuerySet:
    qs = ServiceArea.objects.all().select_related('created_by')
    is_active = query_params.get('is_active')
    if is_active is not None and is_active != '':
        if str(is_active).lower() in ('1', 'true', 'yes'):
            qs = qs.filter(is_active=True)
        elif str(is_active).lower() in ('0', 'false', 'no'):
            qs = qs.filter(is_active=False)
    q = (query_params.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return qs.order_by('name', 'id')


def filter_requests(query_params) -> QuerySet:
    reject_unknown_filters(query_params)
    qs = ServiceAreaRequest.objects.select_related(
        'matched_service_area',
        'customer_profile',
        'customer_profile__user',
    )
    start = _parse_bound(query_params.get('from') or '')
    end = _parse_bound(query_params.get('to') or '', end=True)
    if start is not None:
        qs = qs.filter(requested_at__gte=start)
    if end is not None:
        qs = qs.filter(requested_at__lte=end)

    is_serviceable = query_params.get('is_serviceable')
    if is_serviceable is not None and is_serviceable != '':
        qs = qs.filter(is_serviceable=str(is_serviceable).lower() in ('1', 'true', 'yes'))

    kind = (query_params.get('request_kind') or '').strip()
    if kind:
        if kind not in ServiceAreaRequest.RequestKind.values:
            raise ServiceAreaQueryError(
                'request_kind must be check or demand.',
                code='UNSUPPORTED_FILTER',
            )
        qs = qs.filter(request_kind=kind)

    q = (query_params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(detected_location_name__icontains=q)
            | Q(formatted_address__icontains=q)
            | Q(guest_session_id__icontains=q)
        )
    return qs.order_by('-requested_at', '-id')


def _date_filtered_requests(query_params) -> QuerySet:
    reject_unknown_filters(query_params)
    qs = ServiceAreaRequest.objects.all()
    start = _parse_bound(query_params.get('from') or '')
    end = _parse_bound(query_params.get('to') or '', end=True)
    if start is not None:
        qs = qs.filter(requested_at__gte=start)
    if end is not None:
        qs = qs.filter(requested_at__lte=end)
    return qs


def top_requested_areas(query_params, *, limit: int = 20) -> list[dict]:
    qs = _date_filtered_requests(query_params)
    rows = (
        qs.exclude(detected_location_name='')
        .values('detected_location_name')
        .annotate(request_count=Count('id'))
        .order_by('-request_count', 'detected_location_name')[:limit]
    )
    return [
        {
            'area_name': row['detected_location_name'],
            'request_count': row['request_count'],
        }
        for row in rows
    ]


def top_non_serviceable_areas(query_params, *, limit: int = 20) -> list[dict]:
    qs = _date_filtered_requests(query_params).filter(is_serviceable=False)
    rows = (
        qs.exclude(detected_location_name='')
        .values('detected_location_name')
        .annotate(
            request_count=Count('id'),
            average_distance_km=Avg('distance_km'),
        )
        .order_by('-request_count', 'detected_location_name')[:limit]
    )
    result = []
    for row in rows:
        avg = row['average_distance_km']
        if avg is not None:
            avg = Decimal(str(avg)).quantize(Decimal('0.0001'))
        result.append(
            {
                'area_name': row['detected_location_name'],
                'request_count': row['request_count'],
                'average_distance_km': avg,
            }
        )
    return result


def analytics_summary(query_params) -> dict:
    return {
        'top_requested_areas': top_requested_areas(query_params),
        'top_non_serviceable_areas': top_non_serviceable_areas(query_params),
    }
