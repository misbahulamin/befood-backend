from django.db.models import Q, QuerySet
from django.utils import timezone

from notices.models import Notice

STATUS_DRAFT = 'draft'
STATUS_SCHEDULED = 'scheduled'
STATUS_ACTIVE = 'active'
STATUS_EXPIRED = 'expired'


def get_active_notices(*, at=None) -> QuerySet[Notice]:
    """
    Return notices that are published and within the schedule window at `at`.

    Active rule (UTC):
    - is_published is True
    - publish_at is null OR publish_at <= at
    - publish_until is null OR publish_until > at
    """
    moment = at if at is not None else timezone.now()
    return (
        Notice.objects.filter(is_published=True)
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=moment))
        .filter(Q(publish_until__isnull=True) | Q(publish_until__gt=moment))
        .order_by('sort_order', '-publish_at', '-created_at', '-id')
    )


def compute_lifecycle_status(notice: Notice, *, at=None) -> str:
    """Return draft | scheduled | active | expired for Admin display."""
    moment = at if at is not None else timezone.now()
    if not notice.is_published:
        return STATUS_DRAFT
    if notice.publish_at is not None and notice.publish_at > moment:
        return STATUS_SCHEDULED
    if notice.publish_until is not None and notice.publish_until <= moment:
        return STATUS_EXPIRED
    return STATUS_ACTIVE
