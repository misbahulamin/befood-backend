"""Firebase Cloud Messaging send integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from django.conf import settings


FCM_BATCH_SIZE = 500
logger = logging.getLogger(__name__)


class FCMNotConfiguredError(Exception):
    """Raised when Firebase credentials are missing or invalid."""


@dataclass
class SendResult:
    token: str
    success: bool
    message_id: str = ''
    error: str = ''
    is_invalid_token: bool = False


def _get_firebase_app():
    if not settings.FIREBASE_CREDENTIALS or not os.path.exists(settings.FIREBASE_CREDENTIALS):
        raise FCMNotConfiguredError('Firebase credentials are not configured.')

    import firebase_admin
    from firebase_admin import credentials

    try:
        return firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(str(settings.FIREBASE_CREDENTIALS))
        return firebase_admin.initialize_app(cred)


def _stringify_data(data: dict | None) -> dict[str, str]:
    if not data:
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _classify_error(exc: Exception) -> tuple[str, bool]:
    error_text = str(exc)
    lowered = error_text.lower()
    invalid_markers = (
        'unregistered',
        'registration-token-not-registered',
        'invalid-registration',
        'not registered',
        'invalid-argument',
        'requested entity was not found',
    )
    is_invalid = any(marker in lowered for marker in invalid_markers)
    return error_text, is_invalid


def _android_channel_id(data: dict[str, str]) -> str:
    """Map payload type/screen to mobile NotificationChannels ids."""
    raw_type = (data.get('type') or '').lower()
    screen = (data.get('screen') or '').lower()
    if raw_type.startswith('wallet') or screen in {'wallet', '/wallet'}:
        return 'befood_wallet'
    if raw_type.startswith('delivery') or screen in {
        'delivery_places',
        '/delivery-places',
    }:
        return 'befood_delivery'
    if raw_type.startswith('promotion') or screen in {'offer', '/offer'}:
        return 'befood_promotion'
    return 'befood_order'


def send_to_token(token: str, title: str, body: str, data: dict | None = None) -> SendResult:
    results = send_to_tokens([token], title, body, data)
    return results[0] if results else SendResult(token=token, success=False, error='Empty token list')


def send_to_tokens(tokens: list[str], title: str, body: str, data: dict | None = None) -> list[SendResult]:
    if not tokens:
        return []

    _get_firebase_app()

    from firebase_admin import messaging

    payload_data = _stringify_data(data)
    channel_id = _android_channel_id(payload_data)
    all_results: list[SendResult] = []

    for offset in range(0, len(tokens), FCM_BATCH_SIZE):
        batch = tokens[offset : offset + FCM_BATCH_SIZE]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=payload_data,
            tokens=batch,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id=channel_id,
                ),
            ),
        )
        response = messaging.send_each_for_multicast(message, dry_run=False)
        for index, item in enumerate(response.responses):
            token = batch[index]
            if item.success:
                message_id = item.message_id or ''
                all_results.append(
                    SendResult(token=token, success=True, message_id=message_id)
                )
            else:
                error_text, is_invalid = _classify_error(
                    item.exception or Exception('Unknown FCM error')
                )
                if is_invalid:
                    logger.warning(
                        'FCM invalid token deactivated candidate token_suffix=%s error=%s',
                        token[-8:] if len(token) >= 8 else token,
                        error_text,
                    )
                else:
                    logger.warning(
                        'FCM send failed token_suffix=%s error=%s',
                        token[-8:] if len(token) >= 8 else token,
                        error_text,
                    )
                all_results.append(
                    SendResult(
                        token=token,
                        success=False,
                        error=error_text,
                        is_invalid_token=is_invalid,
                    )
                )

    success_count = sum(1 for r in all_results if r.success)
    fail_count = len(all_results) - success_count
    logger.info(
        'FCM multicast done title=%r success=%s failed=%s channel=%s',
        title,
        success_count,
        fail_count,
        channel_id,
    )
    return all_results
