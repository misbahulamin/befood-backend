from __future__ import annotations

from django.core.cache import cache

from search.models import SearchDocument

CATALOG_CACHE_KEY = 'search:catalog:active:v1'
CATALOG_CACHE_TTL_SECONDS = 60


def invalidate_catalog_cache() -> None:
    cache.delete(CATALOG_CACHE_KEY)


def load_active_catalog(*, force_refresh: bool = False) -> list[SearchDocument]:
    if not force_refresh:
        cached = cache.get(CATALOG_CACHE_KEY)
        if cached is not None:
            return cached

    documents = list(
        SearchDocument.objects.filter(is_active=True)
        .prefetch_related('keywords')
        .order_by('-popularity_score', 'title_en', 'id')
    )
    cache.set(CATALOG_CACHE_KEY, documents, CATALOG_CACHE_TTL_SECONDS)
    return documents
