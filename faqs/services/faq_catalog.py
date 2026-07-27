from django.db.models import Count, Prefetch, Q, QuerySet

from faqs.models import FaqQuestion, FaqType


class FaqTypeDeleteError(Exception):
    """Raised when a FAQ type cannot be deleted because questions remain."""

    def __init__(self, message: str = 'Cannot delete FAQ type while questions exist.'):
        self.message = message
        super().__init__(message)


def get_public_faq_catalog() -> QuerySet[FaqType]:
    """
    Active FAQ types that have at least one published question.

    Nested questions are prefetched with is_published=True only, ordered by
    sort_order ascending.
    """
    published_qs = FaqQuestion.objects.filter(is_published=True).order_by(
        'sort_order',
        'created_at',
        'id',
    )
    return (
        FaqType.objects.filter(is_active=True)
        .annotate(
            published_count=Count(
                'questions',
                filter=Q(questions__is_published=True),
            )
        )
        .filter(published_count__gt=0)
        .prefetch_related(Prefetch('questions', queryset=published_qs))
        .order_by('sort_order', 'created_at', 'id')
    )


def delete_faq_type(faq_type: FaqType) -> None:
    """Hard-delete a type only when it has no questions (PROTECT-safe)."""
    if faq_type.questions.exists():
        raise FaqTypeDeleteError(
            'Cannot delete FAQ type while questions exist. '
            'Delete or move the questions first.'
        )
    faq_type.delete()
