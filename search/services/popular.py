from __future__ import annotations

from django.db.models import Count

from search.models import PopularSearchPin, SearchQueryEvent
from search.services.matching import DEFAULT_SUGGEST_LIMIT, MAX_SUGGEST_LIMIT, clamp_limit


def list_popular_searches(*, limit: int | None = None) -> list[dict]:
    cap = clamp_limit(limit, default=DEFAULT_SUGGEST_LIMIT, maximum=MAX_SUGGEST_LIMIT)
    pins = list(
        PopularSearchPin.objects.filter(is_active=True).order_by('sort_order', 'term')[:cap]
    )
    results: list[dict] = [
        {
            'term': pin.term,
            'term_normalized': pin.term_normalized,
            'source': 'pin',
            'count': None,
        }
        for pin in pins
    ]
    remaining = cap - len(results)
    if remaining <= 0:
        return results[:cap]

    pinned_normalized = {pin.term_normalized for pin in pins}
    rows = (
        SearchQueryEvent.objects.exclude(query_normalized='')
        .values('query_normalized')
        .annotate(count=Count('id'))
        .order_by('-count', 'query_normalized')[: remaining + len(pinned_normalized)]
    )
    for row in rows:
        if row['query_normalized'] in pinned_normalized:
            continue
        results.append(
            {
                'term': row['query_normalized'],
                'term_normalized': row['query_normalized'],
                'source': 'analytics',
                'count': row['count'],
            }
        )
        if len(results) >= cap:
            break
    return results[:cap]
