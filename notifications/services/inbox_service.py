"""Best-effort customer notification inbox persistence."""

from __future__ import annotations

import logging

from django.contrib.contenttypes.models import ContentType

from notifications.models import Notification

logger = logging.getLogger(__name__)


def create_inbox_notification(
    user,
    *,
    title: str,
    body: str,
    notification_type: str = '',
    screen: str = '',
    data: dict | None = None,
    content_object=None,
) -> Notification | None:
    """
    Persist an unread inbox row for [user].

    Optional [content_object] sets the existing GenericForeignKey (e.g. PushCampaign)
    so admin campaign detail can resolve read status.

    When [content_object] is set, re-dispatch dedupes by user + content object so
    stuck-campaign recovery does not create duplicate inbox rows.

    Never raises into callers — FCM send must proceed even if persistence fails.
    """
    try:
        if user is None:
            return None

        if content_object is not None and getattr(content_object, 'pk', None) is not None:
            content_type = ContentType.objects.get_for_model(
                content_object.__class__,
                for_concrete_model=False,
            )
            existing = (
                Notification.objects.filter(
                    user=user,
                    content_type=content_type,
                    object_id=content_object.pk,
                )
                .order_by('id')
                .first()
            )
            if existing is not None:
                return existing

        return Notification.objects.create(
            user=user,
            title=(title or '')[:255],
            body=body or '',
            is_read=False,
            notification_type=(notification_type or '')[:50],
            screen=(screen or '')[:100],
            data=data or {},
            content_object=content_object,
        )
    except Exception:
        logger.exception(
            'Failed to persist inbox notification user_id=%s type=%s',
            getattr(user, 'pk', None),
            notification_type,
        )
        return None
