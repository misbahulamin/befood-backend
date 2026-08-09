from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import IntEnum

from search.models import SearchDocument
from search.services.normalize import normalize_query

DEFAULT_SEARCH_LIMIT = 8
MAX_SEARCH_LIMIT = 20
DEFAULT_SUGGEST_LIMIT = 6
MAX_SUGGEST_LIMIT = 12
MIN_SUGGEST_CHARS = 2
FUZZY_THRESHOLD = 75.0
SHORT_QUERY_FUZZY_THRESHOLD = 85.0


class MatchTier(IntEnum):
    EXACT = 0
    STARTS = 1
    PARTIAL = 2
    KEYWORD = 3
    FUZZY = 4


@dataclass(order=True)
class ScoredDocument:
    tier: int
    neg_popularity: int
    title_sort: str
    public_id_sort: str
    document: SearchDocument = field(compare=False)
    matched_via: str = field(default='', compare=False)
    fuzzy_score: float = field(default=0.0, compare=False)


def _fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def _fuzzy_threshold(query: str) -> float:
    return SHORT_QUERY_FUZZY_THRESHOLD if len(query) <= 3 else FUZZY_THRESHOLD


def _candidate_strings(document: SearchDocument) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for label, raw in (
        ('title_en', document.title_en),
        ('title_bn', document.title_bn),
    ):
        normalized = normalize_query(raw)
        if normalized:
            pairs.append((normalized, label))
    for kw in document.keywords.all():
        if kw.keyword:
            pairs.append((kw.keyword, 'keyword'))
    return pairs


def score_document(document: SearchDocument, query: str) -> ScoredDocument | None:
    if not query:
        return None

    best_tier: MatchTier | None = None
    matched_via = ''
    best_fuzzy = 0.0
    threshold = _fuzzy_threshold(query)

    for text, source in _candidate_strings(document):
        ratio = 0.0
        if text == query:
            candidate = MatchTier.EXACT
        elif text.startswith(query):
            candidate = MatchTier.STARTS
        elif query in text:
            candidate = MatchTier.PARTIAL
        else:
            ratio = _fuzzy_ratio(query, text)
            if ratio < threshold:
                continue
            candidate = MatchTier.FUZZY

        if best_tier is None or candidate < best_tier:
            best_tier = candidate
            matched_via = source
            if candidate == MatchTier.FUZZY:
                best_fuzzy = ratio
        elif candidate == MatchTier.FUZZY and best_tier == MatchTier.FUZZY and ratio > best_fuzzy:
            best_fuzzy = ratio
            matched_via = source

    if best_tier is None:
        return None

    return ScoredDocument(
        tier=int(best_tier),
        neg_popularity=-int(document.popularity_score or 0),
        title_sort=(document.title_en or '').casefold(),
        public_id_sort=str(document.public_id),
        document=document,
        matched_via=matched_via,
        fuzzy_score=best_fuzzy,
    )


def clamp_limit(raw, *, default: int, maximum: int) -> int:
    if raw is None or raw == '':
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum)
