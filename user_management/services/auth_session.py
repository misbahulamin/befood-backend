"""Auth session issue/revoke and unified customer auth response builder."""

from __future__ import annotations

import binascii
import os
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from user_management.models import AuthSession
from user_management.services.identity_verification import (
    build_verification_status,
    safe_user_email,
)
from user_management.services.profile_onboarding import get_onboarding_completion
from user_management.validators import format_bd_phone_e164

DEVICE_TOKEN_BOUND = 'bound'
DEVICE_TOKEN_UNCHANGED = 'unchanged'
DEVICE_TOKEN_OMITTED = 'omitted'
DEVICE_TOKEN_FAILED = 'failed'


def is_phone_verification_required(profile) -> bool:
    """True when the customer must complete phone OTP (soft FE gate)."""
    return not bool(getattr(profile, 'is_phone_verified', False))


def generate_session_key() -> str:
    return binascii.hexlify(os.urandom(20)).decode()


@transaction.atomic
def issue_auth_session(
    user,
    *,
    device_token: str = '',
    platform: str = '',
    user_agent: str = '',
) -> AuthSession:
    """Create a new per-device auth session (does not revoke other sessions)."""
    key = generate_session_key()
    while AuthSession.objects.filter(key=key).exists() or Token.objects.filter(key=key).exists():
        key = generate_session_key()

    return AuthSession.objects.create(
        key=key,
        user=user,
        device_token=(device_token or '').strip(),
        platform=(platform or '').strip(),
        user_agent=(user_agent or '')[:512],
        last_used_at=timezone.now(),
    )


def revoke_auth_session(session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=['revoked_at'])


def revoke_all_auth_sessions(user) -> int:
    """Revoke all AuthSessions and delete legacy DRF Tokens for the user."""
    now = timezone.now()
    updated = AuthSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=now
    )
    Token.objects.filter(user=user).delete()
    return updated


def bind_device_token_on_auth(user, device_token: str | None, platform: str | None) -> dict:
    """
    Soft-fail FCM upsert after successful auth.

    Returns a ``device_token_status`` dict for the unified auth envelope.
    """
    token = (device_token or '').strip()
    plat = (platform or '').strip()
    if not token:
        return {'status': DEVICE_TOKEN_OMITTED}

    from notifications.services.device_service import DeviceTokenError, register_device_token

    try:
        register_device_token(user, token, plat or 'android')
        return {'status': DEVICE_TOKEN_BOUND, 'platform': plat or None}
    except DeviceTokenError as exc:
        return {
            'status': DEVICE_TOKEN_FAILED,
            'detail': exc.message,
            'code': getattr(exc, 'code', 'DEVICE_TOKEN_ERROR'),
        }
    except Exception:
        return {'status': DEVICE_TOKEN_FAILED}


def build_customer_auth_response(
    user,
    *,
    auth_provider: str,
    session: AuthSession | None = None,
    device_token: str | None = None,
    platform: str | None = None,
    user_agent: str = '',
    device_token_status: dict | None = None,
) -> dict[str, Any]:
    """
    Unified auth success envelope for email / phone / google / facebook.

    Issues a new AuthSession when ``session`` is not provided.
    """
    if session is None:
        session = issue_auth_session(
            user,
            device_token=device_token or '',
            platform=platform or '',
            user_agent=user_agent,
        )

    if device_token_status is None:
        device_token_status = bind_device_token_on_auth(user, device_token, platform)

    profile = user.customer_profile
    from user_management.services.location_preference import get_location_confirmation_summary

    return {
        'token': session.key,
        'user': {
            'id': user.id,
            'email': safe_user_email(user),
            'first_name': user.first_name,
            'last_name': user.last_name,
        },
        'groups': list(user.groups.values_list('name', flat=True)),
        'customer_profile': {
            'phone': format_bd_phone_e164(profile.phone),
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'is_email_verified': profile.is_email_verified,
            'is_phone_verified': profile.is_phone_verified,
            'profile_completed': profile.profile_completed,
            'profile_completion_percentage': profile.profile_completion_percentage,
        },
        'device_token_status': device_token_status,
        'auth_provider': auth_provider,
        'phone_verification_required': is_phone_verification_required(profile),
        'has_password': bool(user.has_usable_password()),
        'verification_status': build_verification_status(user),
        'onboarding_completion': get_onboarding_completion(user, profile),
        'location_confirmation': get_location_confirmation_summary(profile),
    }


def force_logout_user(user) -> dict:
    """
    Admin / security force-logout: revoke all sessions and deactivate all FCM tokens.

    Suspicious-login detection may call this later; reserved as the revoke hook.
    """
    from notifications.services.device_service import deactivate_all_user_device_tokens

    sessions_revoked = revoke_all_auth_sessions(user)
    fcm_deactivated = deactivate_all_user_device_tokens(user)
    return {
        'sessions_revoked': sessions_revoked,
        'fcm_tokens_deactivated': fcm_deactivated,
    }


# Alias reserved for future suspicious-login detection product.
suspicious_login_revoke_hook = force_logout_user
