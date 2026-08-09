from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Q, QuerySet
from django.utils.dateparse import parse_date, parse_datetime

from search.models import SearchClickEvent, SearchDocument, SearchQueryEvent

ALLOWED_DOCUMENT_FILTERS = frozenset(
    {
        'document_type',
        'type',
        'is_active',
        'q',
        'page',
        'page_size',
    }
)

ALLOWED_ANALYTICS_FILTERS = frozenset(
    {
        'from',
        'to',
        'page',
        'page_size',
        'kind',
    }
)


class SearchQueryError(Exception):
    def __init__(self, message: str, code: str = 'UNSUPPORTED_FILTER'):
        super().__init__(message)
        self.code = code


def reject_unknown_filters(query_params, allowed: frozenset[str]) -> None:
    unknown = [key for key in query_params.keys() if key not in allowed]
    if unknown:
        raise SearchQueryError(
            f'Unsupported filter(s): {", ".join(sorted(unknown))}',
            code='UNSUPPORTED_FILTER',
        )


def _parse_bound(value: str, *, end: bool = False):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is not None:
        return dt
    day = parse_date(value)
    if day is None:
        raise SearchQueryError(f'Invalid date value: {value}', code='UNSUPPORTED_FILTER')
    if end:
        return datetime.combine(day, datetime.max.time())
    return datetime.combine(day, datetime.min.time())


def filter_documents(query_params) -> QuerySet:
    reject_unknown_filters(query_params, ALLOWED_DOCUMENT_FILTERS)
    qs = SearchDocument.objects.all().prefetch_related('keywords')
    doc_type = query_params.get('document_type') or query_params.get('type')
    if doc_type:
        qs = qs.filter(document_type=doc_type)
    is_active = query_params.get('is_active')
    if is_active is not None and is_active != '':
        if str(is_active).lower() in ('1', 'true', 'yes'):
            qs = qs.filter(is_active=True)
        elif str(is_active).lower() in ('0', 'false', 'no'):
            qs = qs.filter(is_active=False)
    q = (query_params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(title_en__icontains=q)
            | Q(title_bn__icontains=q)
            | Q(short_description__icontains=q)
            | Q(keywords__keyword_raw__icontains=q)
            | Q(keywords__keyword__icontains=q)
        ).distinct()
    return qs.order_by('-popularity_score', 'title_en', 'id')


def analytics_summary(query_params) -> dict:
    reject_unknown_filters(query_params, ALLOWED_ANALYTICS_FILTERS)
    start = _parse_bound(query_params.get('from') or '')
    end = _parse_bound(query_params.get('to') or '', end=True)

    queries = SearchQueryEvent.objects.all()
    clicks = SearchClickEvent.objects.select_related('document')
    if start is not None:
        queries = queries.filter(created_at__gte=start)
        clicks = clicks.filter(created_at__gte=start)
    if end is not None:
        queries = queries.filter(created_at__lte=end)
        clicks = clicks.filter(created_at__lte=end)

    top_queries = list(
        queries.exclude(query_normalized='')
        .values('query_normalized')
        .annotate(count=Count('id'))
        .order_by('-count', 'query_normalized')[:20]
    )
    zero_result_queries = list(
        queries.filter(is_zero_result=True)
        .exclude(query_normalized='')
        .values('query_normalized')
        .annotate(count=Count('id'))
        .order_by('-count', 'query_normalized')[:20]
    )
    top_clicked = list(
        clicks.filter(document__isnull=False)
        .values(
            'document__public_id',
            'document__title_en',
            'clicked_type',
        )
        .annotate(count=Count('id'))
        .order_by('-count')[:20]
    )
    return {
        'top_queries': [
            {'query': row['query_normalized'], 'count': row['count']} for row in top_queries
        ],
        'zero_result_queries': [
            {'query': row['query_normalized'], 'count': row['count']}
            for row in zero_result_queries
        ],
        'top_clicked': [
            {
                'public_id': str(row['document__public_id']),
                'title_en': row['document__title_en'],
                'type': row['clicked_type'],
                'count': row['count'],
            }
            for row in top_clicked
        ],
    }
