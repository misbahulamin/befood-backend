from django.db.models import Q, QuerySet
from django.utils import timezone

from announcements.models import Announcement

STATUS_DRAFT = 'draft'
STATUS_SCHEDULED = 'scheduled'
STATUS_ACTIVE = 'active'
STATUS_EXPIRED = 'expired'


def get_active_announcements(*, at=None) -> QuerySet[Announcement]:
    """
    Return announcements that are published and within the schedule window at `at`.

    Active rule (UTC):
    - is_published is True
    - publish_at is null OR publish_at <= at
    - publish_until is null OR publish_until >= at  (inclusive end)
    """
    moment = at if at is not None else timezone.now()
    return (
        Announcement.objects.filter(is_published=True)
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=moment))
        .filter(Q(publish_until__isnull=True) | Q(publish_until__gte=moment))
        .order_by('-priority', '-created_at', '-id')
    )


def compute_lifecycle_status(announcement: Announcement, *, at=None) -> str:
    """Return draft | scheduled | active | expired for Admin display."""
    moment = at if at is not None else timezone.now()
    if not announcement.is_published:
        return STATUS_DRAFT
    if announcement.publish_at is not None and announcement.publish_at > moment:
        return STATUS_SCHEDULED
    if (
        announcement.publish_until is not None
        and announcement.publish_until < moment
    ):
        return STATUS_EXPIRED
    return STATUS_ACTIVE
