"""Admin push campaign creation and async dispatch."""

from __future__ import annotations

import logging
import threading
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from notifications.models import PushCampaign, PushCampaignRecipient
from notifications.services.device_service import deactivate_device_token_by_value
from notifications.services.fcm_service import FCMNotConfiguredError, send_to_tokens
from notifications.services.inbox_service import create_inbox_notification
from notifications.services.notification_filter import (
    TARGET_TYPE_MAP,
    count_eligible_users,
    normalize_target_config,
    resolve_delivery_targets,
    resolve_target_users,
)

logger = logging.getLogger(__name__)

BROADCAST_CONFIRMATION_THRESHOLD = 1000
IDEMPOTENCY_KEY_TTL_HOURS = 24
FINGERPRINT_DEDUP_MINUTES = 5
RECIPIENT_BULK_SIZE = 1000
STUCK_CAMPAIGN_MINUTES = 30

_DEFAULT_SCREEN_BY_TYPE = {
    'order': 'my_meal',
    'wallet': 'wallet',
    'delivery': 'delivery_places',
    'promotion': 'offer',
    'system': 'home',
}


def _with_navigable_data(data: dict | None, notification_type: str) -> dict:
    payload = dict(data or {})
    if notification_type and 'type' not in payload:
        payload['type'] = notification_type
    if 'screen' not in payload:
        default_screen = _DEFAULT_SCREEN_BY_TYPE.get(str(notification_type).lower())
        if default_screen:
            payload['screen'] = default_screen
    return payload


class DuplicateCampaignError(Exception):
    def __init__(self, campaign: PushCampaign):
        self.campaign = campaign
        super().__init__('Duplicate campaign detected.')


class BroadcastConfirmationRequiredError(Exception):
    def __init__(self, eligible_count: int):
        self.eligible_count = eligible_count
        super().__init__('Broadcast confirmation required.')


def _find_idempotent_campaign(created_by, idempotency_key: str) -> PushCampaign | None:
    if not idempotency_key:
        return None
    cutoff = timezone.now() - timedelta(hours=IDEMPOTENCY_KEY_TTL_HOURS)
    return (
        PushCampaign.objects.filter(
            created_by=created_by,
            idempotency_key=idempotency_key,
            created_at__gte=cutoff,
        )
        .order_by('-created_at')
        .first()
    )


def _find_fingerprint_duplicate(
    created_by,
    title: str,
    body: str,
    target_config: dict,
) -> PushCampaign | None:
    cutoff = timezone.now() - timedelta(minutes=FINGERPRINT_DEDUP_MINUTES)
    return (
        PushCampaign.objects.filter(
            created_by=created_by,
            title=title.strip(),
            body=body.strip(),
            target_config=target_config,
            created_at__gte=cutoff,
        )
        .order_by('-created_at')
        .first()
    )


def _ensure_broadcast_confirmed(target: dict) -> None:
    if target.get('type') != 'all':
        return
    eligible = count_eligible_users(target)
    if eligible > BROADCAST_CONFIRMATION_THRESHOLD and not target.get('confirm_broadcast'):
        raise BroadcastConfirmationRequiredError(eligible)


@transaction.atomic
def create_campaign(
    *,
    created_by,
    title: str,
    body: str,
    notification_type: str,
    data: dict,
    target: dict,
    ip_address: str | None,
    user_agent: str,
    idempotency_key: str = '',
) -> tuple[PushCampaign, bool]:
    normalized_target = normalize_target_config(target)
    target_type = TARGET_TYPE_MAP.get(normalized_target['type'])
    if not target_type:
        raise ValueError('Invalid target type')

    existing = _find_idempotent_campaign(created_by, idempotency_key)
    if existing:
        return existing, False

    duplicate = _find_fingerprint_duplicate(created_by, title, body, normalized_target)
    if duplicate and not idempotency_key:
        raise DuplicateCampaignError(duplicate)

    _ensure_broadcast_confirmed(normalized_target)
    users_qs = resolve_target_users(normalized_target)
    user_ids = list(users_qs.values_list('id', flat=True))
    delivery_rows = resolve_delivery_targets(user_ids)

    campaign = PushCampaign.objects.create(
        title=title.strip(),
        body=body.strip(),
        notification_type=notification_type,
        data=_with_navigable_data(data, notification_type),
        created_by=created_by,
        ip_address=ip_address or None,
        user_agent=(user_agent or '')[:512],
        idempotency_key=(idempotency_key or '')[:128],
        target_type=target_type,
        target_config=normalized_target,
        status=PushCampaign.Status.PROCESSING,
        total_targets=len(user_ids),
    )

    recipient_objects = [
        PushCampaignRecipient(
            campaign=campaign,
            user_id=row['user_id'],
            device_id=row['device_id'],
            status=row['status'],
            error_message=row['error_message'],
        )
        for row in delivery_rows
    ]
    if recipient_objects:
        PushCampaignRecipient.objects.bulk_create(recipient_objects, batch_size=RECIPIENT_BULK_SIZE)

    skipped = sum(1 for row in delivery_rows if row['status'] == 'skipped')
    failed = sum(1 for row in delivery_rows if row['status'] == 'failed')
    if skipped or failed:
        campaign.total_skipped = skipped
        campaign.total_failed = failed
        campaign.save(update_fields=['total_skipped', 'total_failed', 'updated_at'])

    return campaign, True


def enqueue_dispatch(campaign_id: int) -> None:
    thread = threading.Thread(
        target=dispatch_push_campaign,
        args=(campaign_id,),
        daemon=True,
        name=f'push-campaign-{campaign_id}',
    )
    thread.start()


def dispatch_push_campaign(campaign_id: int) -> None:
    try:
        campaign = PushCampaign.objects.get(pk=campaign_id)
    except PushCampaign.DoesNotExist:
        logger.warning('Push campaign %s not found for dispatch', campaign_id)
        return

    if campaign.status not in (
        PushCampaign.Status.PENDING,
        PushCampaign.Status.PROCESSING,
    ):
        return

    campaign.status = PushCampaign.Status.PROCESSING
    campaign.save(update_fields=['status', 'updated_at'])

    pending_recipients = list(
        PushCampaignRecipient.objects.filter(
            campaign=campaign,
            status=PushCampaignRecipient.Status.PENDING,
            device__isnull=False,
        ).select_related('device')
    )

    token_map: dict[str, PushCampaignRecipient] = {}
    tokens: list[str] = []
    for recipient in pending_recipients:
        token = recipient.device.token
        if not token:
            recipient.status = PushCampaignRecipient.Status.FAILED
            recipient.error_message = 'Empty device token'
            recipient.save(update_fields=['status', 'error_message'])
            continue
        token_map[token] = recipient
        tokens.append(token)

    sent = 0
    failed = campaign.total_failed
    skipped = campaign.total_skipped

    if not tokens and not pending_recipients:
        campaign.status = PushCampaign.Status.COMPLETED
        campaign.total_sent = 0
        campaign.total_failed = failed
        campaign.total_skipped = skipped
        campaign.save(
            update_fields=['status', 'total_sent', 'total_failed', 'total_skipped', 'updated_at']
        )
        return

    # One inbox row per unique user (best-effort; never blocks FCM).
    inbox_users = {recipient.user for recipient in pending_recipients if recipient.user_id}
    campaign_data = campaign.data if isinstance(campaign.data, dict) else {}
    for user in inbox_users:
        create_inbox_notification(
            user,
            title=campaign.title,
            body=campaign.body,
            notification_type=campaign.notification_type or campaign_data.get('type', ''),
            screen=str(campaign_data.get('screen') or ''),
            data=campaign_data,
        )

    try:
        results = send_to_tokens(tokens, campaign.title, campaign.body, campaign.data)
    except FCMNotConfiguredError as exc:
        campaign.status = PushCampaign.Status.FAILED
        campaign.error_summary = str(exc)
        campaign.save(update_fields=['status', 'error_summary', 'updated_at'])
        PushCampaignRecipient.objects.filter(
            campaign=campaign,
            status=PushCampaignRecipient.Status.PENDING,
        ).update(
            status=PushCampaignRecipient.Status.FAILED,
            error_message=str(exc),
        )
        return

    now = timezone.now()
    for result in results:
        recipient = token_map.get(result.token)
        if recipient is None:
            continue
        if result.success:
            recipient.status = PushCampaignRecipient.Status.SENT
            recipient.firebase_message_id = result.message_id
            recipient.sent_at = now
            recipient.error_message = ''
            sent += 1
        else:
            recipient.status = PushCampaignRecipient.Status.FAILED
            recipient.error_message = result.error
            failed += 1
            if result.is_invalid_token:
                deactivate_device_token_by_value(result.token)
        recipient.save(
            update_fields=['status', 'firebase_message_id', 'error_message', 'sent_at']
        )

    campaign.status = PushCampaign.Status.COMPLETED
    campaign.total_sent = sent
    campaign.total_failed = failed
    campaign.total_skipped = skipped
    campaign.save(
        update_fields=['status', 'total_sent', 'total_failed', 'total_skipped', 'updated_at']
    )


def get_stuck_campaign_ids() -> list[int]:
    cutoff = timezone.now() - timedelta(minutes=STUCK_CAMPAIGN_MINUTES)
    return list(
        PushCampaign.objects.filter(
            status=PushCampaign.Status.PROCESSING,
            updated_at__lt=cutoff,
        ).values_list('id', flat=True)
    )
