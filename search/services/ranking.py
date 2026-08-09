from __future__ import annotations

from dataclasses import dataclass

from search.models import SearchDocument
from search.services.catalog_cache import load_active_catalog
from search.services.matching import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SUGGEST_LIMIT,
    MAX_SEARCH_LIMIT,
    MAX_SUGGEST_LIMIT,
    MIN_SUGGEST_CHARS,
    MatchTier,
    ScoredDocument,
    clamp_limit,
    score_document,
)
from search.services.normalize import normalize_query


@dataclass
class SearchOutcome:
    query_original: str
    query_normalized: str
    results: list[ScoredDocument]
    did_you_mean: str | None
    related: list[SearchDocument]
    strong_match_count: int


def _filter_type(documents: list[SearchDocument], document_type: str | None) -> list[SearchDocument]:
    if not document_type:
        return documents
    return [d for d in documents if d.document_type == document_type]


def rank_documents(
    query_original: str,
    *,
    document_type: str | None = None,
    limit: int | None = None,
    catalog: list[SearchDocument] | None = None,
) -> SearchOutcome:
    normalized = normalize_query(query_original)
    cap = clamp_limit(limit, default=DEFAULT_SEARCH_LIMIT, maximum=MAX_SEARCH_LIMIT)
    if not normalized:
        return SearchOutcome(
            query_original=query_original or '',
            query_normalized='',
            results=[],
            did_you_mean=None,
            related=[],
            strong_match_count=0,
        )

    docs = _filter_type(catalog if catalog is not None else load_active_catalog(), document_type)
    scored: list[ScoredDocument] = []
    for document in docs:
        item = score_document(document, normalized)
        if item is not None:
            scored.append(item)
    scored.sort()

    strong = [s for s in scored if s.tier <= MatchTier.PARTIAL]
    weak_fuzzy = [s for s in scored if s.tier == MatchTier.FUZZY]
    primary = strong if strong else scored
    results = primary[:cap]
    strong_match_count = len(strong)

    did_you_mean = None
    related: list[SearchDocument] = []

    if not results:
        if weak_fuzzy:
            top = weak_fuzzy[0]
            did_you_mean = top.document.display_name
            related = [s.document for s in weak_fuzzy[:cap]]
        else:
            related = sorted(
                docs,
                key=lambda d: (-d.popularity_score, d.title_en, str(d.public_id)),
            )[:cap]
    elif strong_match_count == 0 and results:
        # Only fuzzy primary results — still expose did_you_mean from best fuzzy.
        did_you_mean = results[0].document.display_name

    return SearchOutcome(
        query_original=query_original or '',
        query_normalized=normalized,
        results=results,
        did_you_mean=did_you_mean,
        related=related,
        strong_match_count=strong_match_count,
    )


def suggest_documents(
    query_original: str,
    *,
    document_type: str | None = None,
    limit: int | None = None,
    catalog: list[SearchDocument] | None = None,
) -> SearchOutcome:
    normalized = normalize_query(query_original)
    cap = clamp_limit(limit, default=DEFAULT_SUGGEST_LIMIT, maximum=MAX_SUGGEST_LIMIT)
    if len(normalized) < MIN_SUGGEST_CHARS:
        return SearchOutcome(
            query_original=query_original or '',
            query_normalized=normalized,
            results=[],
            did_you_mean=None,
            related=[],
            strong_match_count=0,
        )

    outcome = rank_documents(
        query_original,
        document_type=document_type,
        limit=cap,
        catalog=catalog,
    )
    # Suggestions prefer exact/starts/partial over fuzzy-only noise for short prefixes.
    filtered = [s for s in outcome.results if s.tier <= MatchTier.PARTIAL]
    if not filtered and len(normalized) >= 4:
        filtered = outcome.results
    outcome.results = filtered[:cap]
    outcome.related = []
    outcome.did_you_mean = None
    return outcome
