from django.db.models import F, QuerySet
from django.utils import timezone
from rest_framework import serializers

from blogs.models import BlogArticle

DEFAULT_POPULAR_LIMIT = 5
MAX_POPULAR_LIMIT = 20
DEFAULT_RELATED_LIMIT = 4
MAX_RELATED_LIMIT = 12


def _clamp_limit(limit, *, default: int, maximum: int) -> int:
    if limit is None:
        return default
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum)


def get_public_article_queryset() -> QuerySet[BlogArticle]:
    """Published articles for public APIs, with category/author joined."""
    return (
        BlogArticle.objects.filter(is_published=True, published_at__isnull=False)
        .select_related('category', 'author')
        .order_by('-published_at', '-id')
    )


def increment_article_views(article: BlogArticle) -> None:
    """Atomically increment view_count (race-safe)."""
    BlogArticle.objects.filter(pk=article.pk).update(view_count=F('view_count') + 1)
    article.refresh_from_db(fields=['view_count'])


def get_popular_articles(limit=None) -> QuerySet[BlogArticle]:
    """Highest view_count published articles for the Most Popular widget."""
    clamped = _clamp_limit(
        limit,
        default=DEFAULT_POPULAR_LIMIT,
        maximum=MAX_POPULAR_LIMIT,
    )
    return get_public_article_queryset().order_by(
        '-view_count',
        '-published_at',
        '-id',
    )[:clamped]


def get_related_articles(article: BlogArticle, limit=None) -> list[BlogArticle]:
    """
    Related published articles: prefer same category, then global backfill.
    Excludes the source article. Empty list is valid.
    """
    clamped = _clamp_limit(
        limit,
        default=DEFAULT_RELATED_LIMIT,
        maximum=MAX_RELATED_LIMIT,
    )
    if clamped < 1:
        return []

    base = get_public_article_queryset().exclude(pk=article.pk).order_by(
        '-view_count',
        '-published_at',
        '-id',
    )
    selected: list[BlogArticle] = []
    selected_ids: set[int] = set()

    if article.category_id is not None:
        for row in base.filter(category_id=article.category_id)[:clamped]:
            selected.append(row)
            selected_ids.add(row.pk)

    if len(selected) < clamped:
        remaining = clamped - len(selected)
        for row in base.exclude(pk__in=selected_ids)[:remaining]:
            selected.append(row)
            selected_ids.add(row.pk)

    return selected


def apply_publish_state(article: BlogArticle) -> None:
    """
    Apply publish lifecycle rules on an article instance (before save).

    - First publish (is_published True, published_at null) sets published_at now.
    - Unpublish keeps historical published_at.
    - Publishing requires cover_image (raises DRF ValidationError).
    """
    if article.is_published:
        if not article.cover_image:
            raise serializers.ValidationError(
                {'cover_image': 'Cover image is required when publishing.'}
            )
        if article.published_at is None:
            article.published_at = timezone.now()
    # Unpublish: leave published_at unchanged intentionally.
