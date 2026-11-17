"""Firebase Cloud Messaging send integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from django.conf import settings


FCM_BATCH_SIZE = 500
logger = logging.getLogger(__name__)

# Platforms that use native Android/iOS FCM payload (no WebpushConfig).
_NATIVE_PLATFORMS = frozenset({'android', 'ios', ''})


class FCMNotConfiguredError(Exception):
    """Raised when Firebase credentials are missing or invalid."""


class FCMSendError(Exception):
    """
    Controlled FCM/SDK failure that campaign dispatch can finalize safely.

    [results] may contain per-token outcomes already collected before the failure.
    """

    def __init__(self, message: str, *, results: list[SendResult] | None = None):
        self.results = results or []
        super().__init__(message)


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
    """
    Return (error_text, is_invalid_token).

    Only clearly unregistered/invalid registration-token errors mark a token
    for deactivation. Broad markers such as ``invalid-argument`` (often from
    payload/config mistakes) must NOT deactivate healthy tokens.
    """
    error_text = str(exc)
    lowered = error_text.lower()
    invalid_markers = (
        'unregistered',
        'registration-token-not-registered',
        'invalid-registration',
        'not registered',
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


def _web_click_link(payload_data: dict[str, str]) -> str:
    link = payload_data.get('screen') or '/notifications'
    if link and not str(link).startswith('/'):
        # Logical screen keys — fall back to inbox for web click targets.
        link = '/notifications'
    return str(link)


def _resolve_token_platforms(
    tokens: list[str],
    token_platforms: dict[str, str] | None,
) -> dict[str, str]:
    """Map each token to a platform; unknown tokens default to android (native)."""
    if token_platforms is not None:
        return {token: (token_platforms.get(token) or 'android') for token in tokens}

    from user_management.models import DeviceToken

    found = dict(
        DeviceToken.objects.filter(token__in=tokens).values_list('token', 'platform')
    )
    return {token: (found.get(token) or 'android') for token in tokens}


def _results_from_response(batch: list[str], response) -> list[SendResult]:
    results: list[SendResult] = []
    for index, item in enumerate(response.responses):
        token = batch[index]
        if item.success:
            results.append(
                SendResult(token=token, success=True, message_id=item.message_id or '')
            )
            continue
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
        results.append(
            SendResult(
                token=token,
                success=False,
                error=error_text,
                is_invalid_token=is_invalid,
            )
        )
    return results


def _failure_results(tokens: list[str], error: str) -> list[SendResult]:
    return [
        SendResult(token=token, success=False, error=error, is_invalid_token=False)
        for token in tokens
    ]


def _send_platform_batches(
    tokens: list[str],
    title: str,
    body: str,
    payload_data: dict[str, str],
    *,
    platform_kind: str,
) -> list[SendResult]:
    """
    Send [tokens] in chunks of FCM_BATCH_SIZE.

    [platform_kind] is ``native`` (AndroidConfig only) or ``web`` (WebpushConfig).
    Unexpected SDK exceptions become per-token failure results for that batch
    so callers can always finalize recipient rows.
    """
    if not tokens:
        return []

    from firebase_admin import messaging

    channel_id = _android_channel_id(payload_data)
    link = _web_click_link(payload_data)
    all_results: list[SendResult] = []

    for offset in range(0, len(tokens), FCM_BATCH_SIZE):
        batch = tokens[offset : offset + FCM_BATCH_SIZE]
        kwargs: dict = {
            'notification': messaging.Notification(title=title, body=body),
            'data': payload_data,
            'tokens': batch,
        }
        if platform_kind == 'native':
            kwargs['android'] = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(channel_id=channel_id),
            )
        else:
            kwargs['webpush'] = messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(link=link),
            )

        message = messaging.MulticastMessage(**kwargs)
        try:
            response = messaging.send_each_for_multicast(message, dry_run=False)
        except Exception as exc:
            # Do not raise out of a single batch — return controlled failures so
            # mixed-platform campaigns can still complete other platform batches.
            safe_error = f'FCM send error: {exc.__class__.__name__}'
            logger.exception(
                'Unexpected FCM batch failure kind=%s size=%s',
                platform_kind,
                len(batch),
            )
            all_results.extend(_failure_results(batch, safe_error))
            continue
        all_results.extend(_results_from_response(batch, response))

    return all_results


def send_to_token(token: str, title: str, body: str, data: dict | None = None) -> SendResult:
    results = send_to_tokens([token], title, body, data)
    return results[0] if results else SendResult(token=token, success=False, error='Empty token list')


def send_to_tokens(
    tokens: list[str],
    title: str,
    body: str,
    data: dict | None = None,
    *,
    token_platforms: dict[str, str] | None = None,
) -> list[SendResult]:
    """
    Send FCM multicast, splitting native vs web tokens into separate batches.

    Optional [token_platforms] maps token -> platform. When omitted, platforms
    are resolved from ``DeviceToken`` (unknown tokens treated as android).
    """
    if not tokens:
        return []

    _get_firebase_app()

    payload_data = _stringify_data(data)
    channel_id = _android_channel_id(payload_data)
    platforms = _resolve_token_platforms(tokens, token_platforms)

    native_tokens = [
        token for token in tokens if (platforms.get(token) or 'android') in _NATIVE_PLATFORMS
    ]
    web_tokens = [
        token for token in tokens if (platforms.get(token) or 'android') == 'web'
    ]

    all_results: list[SendResult] = []
    try:
        all_results.extend(
            _send_platform_batches(
                native_tokens,
                title,
                body,
                payload_data,
                platform_kind='native',
            )
        )
        all_results.extend(
            _send_platform_batches(
                web_tokens,
                title,
                body,
                payload_data,
                platform_kind='web',
            )
        )
    except FCMNotConfiguredError:
        raise
    except Exception as exc:
        # Campaign-level unexpected failure after init — raise typed error with
        # any partial results so dispatch can finalize pending recipients.
        safe_message = f'FCM send error: {exc.__class__.__name__}'
        logger.exception('Unexpected FCM send failure title=%r', title)
        raise FCMSendError(safe_message, results=all_results) from exc

    success_count = sum(1 for r in all_results if r.success)
    fail_count = len(all_results) - success_count
    logger.info(
        'FCM multicast done title=%r success=%s failed=%s channel=%s native=%s web=%s',
        title,
        success_count,
        fail_count,
        channel_id,
        len(native_tokens),
        len(web_tokens),
    )
    return all_results
