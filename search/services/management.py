from __future__ import annotations

from django.db import transaction

from search.models import SearchDocument, SearchKeyword
from search.services.catalog_cache import invalidate_catalog_cache
from search.services.indexing import add_keyword
from search.services.normalize import normalize_query


class SearchManagementError(Exception):
    def __init__(self, message: str, code: str = 'SEARCH_MANAGEMENT_ERROR', errors=None):
        super().__init__(message)
        self.code = code
        self.errors = errors or {}


@transaction.atomic
def create_document(**fields) -> SearchDocument:
    keywords = fields.pop('keywords', None)
    document = SearchDocument.objects.create(**fields)
    if keywords:
        for item in keywords:
            raw = item.get('keyword_raw') or item.get('keyword')
            locale = item.get('locale_hint', 'other')
            try:
                add_keyword(document, raw, locale_hint=locale, raise_on_duplicate=True)
            except ValueError as exc:
                raise SearchManagementError(str(exc), code='DUPLICATE_KEYWORD') from exc
    invalidate_catalog_cache()
    return document


@transaction.atomic
def update_document(document: SearchDocument, **fields) -> SearchDocument:
    for key, value in fields.items():
        setattr(document, key, value)
    document.save()
    invalidate_catalog_cache()
    return document


def deactivate_document(document: SearchDocument) -> SearchDocument:
    document.is_active = False
    document.save(update_fields=['is_active', 'updated_at'])
    invalidate_catalog_cache()
    return document


@transaction.atomic
def create_document_keyword(
    document: SearchDocument,
    *,
    keyword_raw: str,
    locale_hint: str = 'other',
) -> SearchKeyword:
    try:
        keyword = add_keyword(
            document,
            keyword_raw,
            locale_hint=locale_hint,
            raise_on_duplicate=True,
        )
    except ValueError as exc:
        raise SearchManagementError(str(exc), code='DUPLICATE_KEYWORD') from exc
    invalidate_catalog_cache()
    return keyword


def delete_document_keyword(keyword: SearchKeyword) -> None:
    keyword.delete()
    invalidate_catalog_cache()


def upsert_popular_pin(*, term: str, sort_order: int = 0, is_active: bool = True):
    from search.models import PopularSearchPin

    normalized = normalize_query(term)
    if not normalized:
        raise SearchManagementError('Popular term is empty after normalization.')
    pin, _ = PopularSearchPin.objects.update_or_create(
        term_normalized=normalized,
        defaults={
            'term': term.strip(),
            'sort_order': sort_order,
            'is_active': is_active,
        },
    )
    return pin
