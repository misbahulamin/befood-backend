"""Best-effort customer notification inbox persistence."""

from __future__ import annotations

import logging

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

    Never raises into callers — FCM send must proceed even if persistence fails.
    """
    try:
        if user is None:
            return None
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
