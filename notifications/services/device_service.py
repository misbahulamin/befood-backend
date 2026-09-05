"""FCM device token storage and query services."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from user_management.models import DeviceToken

MIN_TOKEN_LENGTH = 10
MAX_TOKEN_LENGTH = 255


class DeviceTokenError(Exception):
    def __init__(self, message: str, code: str = 'DEVICE_TOKEN_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def normalize_token(token: str) -> str:
    return (token or '').strip()


def validate_token(token: str) -> None:
    if not token:
        raise DeviceTokenError('Token is required.', 'TOKEN_REQUIRED')
    if len(token) < MIN_TOKEN_LENGTH:
        raise DeviceTokenError(
            f'Token must be at least {MIN_TOKEN_LENGTH} characters.',
            'TOKEN_TOO_SHORT',
        )
    if len(token) > MAX_TOKEN_LENGTH:
        raise DeviceTokenError(
            f'Token must be at most {MAX_TOKEN_LENGTH} characters.',
            'TOKEN_TOO_LONG',
        )


@transaction.atomic
def register_device_token(
    user,
    token: str,
    platform: str,
    device_name: str = '',
    app_version: str = '',
) -> DeviceToken:
    normalized = normalize_token(token)
    validate_token(normalized)

    now = timezone.now()
    device, _created = DeviceToken.objects.update_or_create(
        token=normalized,
        defaults={
            'user': user,
            'platform': platform,
            'device_name': (device_name or '').strip(),
            'app_version': (app_version or '').strip(),
            'is_active': True,
            'last_used_at': now,
        },
    )
    return device


def deactivate_device_token(user, token: str) -> bool:
    """
    Soft-deactivate a token owned by the given user.

    Returns True when the caller owns the token (including already inactive).
    Returns False when the token does not exist or belongs to another user.
    """
    normalized = normalize_token(token)
    validate_token(normalized)

    try:
        device = DeviceToken.objects.get(token=normalized)
    except DeviceToken.DoesNotExist:
        return False

    if device.user_id != user.id:
        return False

    if device.is_active:
        device.is_active = False
        device.save(update_fields=['is_active', 'updated_at'])
    return True


def get_user_device_tokens(user) -> list[str]:
    return list(
        DeviceToken.objects.filter(user=user, is_active=True)
        .exclude(token='')
        .values_list('token', flat=True)
    )


def get_all_active_device_tokens():
    return (
        DeviceToken.objects.filter(is_active=True)
        .exclude(token='')
        .values_list('token', flat=True)
    )


def deactivate_device_token_by_value(token: str) -> bool:
    """Soft-deactivate a token by value (system-initiated, no ownership check)."""
    normalized = normalize_token(token)
    if not normalized:
        return False
    updated = DeviceToken.objects.filter(token=normalized, is_active=True).update(
        is_active=False,
        updated_at=timezone.now(),
    )
    return updated > 0


def deactivate_all_user_device_tokens(user) -> int:
    """Soft-deactivate every active FCM token for the user. Returns count updated."""
    return DeviceToken.objects.filter(user=user, is_active=True).update(
        is_active=False,
        updated_at=timezone.now(),
    )
