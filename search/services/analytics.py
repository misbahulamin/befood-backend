from __future__ import annotations

import logging

from django.contrib.auth.models import AbstractBaseUser

from search.models import SearchClickEvent, SearchDocument, SearchQueryEvent
from search.services.normalize import normalize_query

logger = logging.getLogger(__name__)


def record_query_event(
    *,
    query_original: str,
    query_normalized: str | None = None,
    result_count: int,
    user: AbstractBaseUser | None = None,
    session_id: str = '',
) -> SearchQueryEvent | None:
    try:
        normalized = query_normalized if query_normalized is not None else normalize_query(query_original)
        return SearchQueryEvent.objects.create(
            query_original=(query_original or '')[:255],
            query_normalized=(normalized or '')[:255],
            result_count=max(0, int(result_count)),
            is_zero_result=int(result_count) <= 0,
            user=user if getattr(user, 'is_authenticated', False) else None,
            session_id=(session_id or '')[:64],
        )
    except Exception:
        logger.exception('Failed to persist search query analytics')
        return None


def record_click_event(
    *,
    document: SearchDocument,
    query_original: str = '',
    query_normalized: str = '',
    position: int | None = None,
    query_event: SearchQueryEvent | None = None,
    user: AbstractBaseUser | None = None,
    session_id: str = '',
) -> SearchClickEvent:
    normalized = query_normalized or normalize_query(query_original)
    return SearchClickEvent.objects.create(
        query_event=query_event,
        query_original=(query_original or '')[:255],
        query_normalized=(normalized or '')[:255],
        document=document,
        clicked_type=document.document_type,
        position=position,
        user=user if getattr(user, 'is_authenticated', False) else None,
        session_id=(session_id or '')[:64],
    )
