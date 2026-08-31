"""Customer auth OTP helpers (hashed codes; purpose-isolated)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from user_management.models import CustomerAuthOTP

PURPOSE_EMAIL_VERIFICATION = CustomerAuthOTP.Purpose.EMAIL_VERIFICATION
PURPOSE_PASSWORD_RESET = CustomerAuthOTP.Purpose.PASSWORD_RESET

OTP_INVALID_MESSAGE = 'Invalid or expired OTP.'
OTP_EXPIRED_MESSAGE = 'OTP expired.'
OTP_RATE_LIMITED_MESSAGE = 'Too many OTP requests. Please try again later.'


class IssueStatus(str, Enum):
    ISSUED = 'issued'
    REUSED = 'reused'
    RATE_LIMITED = 'rate_limited'


@dataclass(frozen=True)
class IssueResult:
    status: IssueStatus
    plaintext_otp: str | None = None
    record: CustomerAuthOTP | None = None


class AuthOTPError(Exception):
    """Raised when OTP verification fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _ttl_seconds() -> int:
    return int(getattr(settings, 'AUTH_OTP_TTL_SECONDS', 600))


def _max_attempts() -> int:
    return int(getattr(settings, 'AUTH_OTP_MAX_ATTEMPTS', 5))


def _cooldown_seconds() -> int:
    return int(getattr(settings, 'AUTH_OTP_RESEND_COOLDOWN_SECONDS', 60))


def _max_issues_per_hour() -> int:
    return int(getattr(settings, 'AUTH_OTP_MAX_ISSUES_PER_HOUR', 10))


def _hmac_key() -> bytes:
    key = getattr(settings, 'AUTH_OTP_HMAC_KEY', None) or settings.SECRET_KEY
    return key.encode('utf-8') if isinstance(key, str) else key


def generate_otp_code() -> str:
    return f'{secrets.randbelow(1_000_000):06d}'


def hash_otp_code(code: str) -> str:
    digest = hmac.new(_hmac_key(), code.encode('utf-8'), hashlib.sha256).hexdigest()
    return digest


def codes_match(plaintext: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp_code(plaintext), code_hash)


def get_active_otp(user, purpose: str):
    now = timezone.now()
    return (
        CustomerAuthOTP.objects.filter(
            user=user,
            purpose=purpose,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by('-created_at')
        .first()
    )


def invalidate_active_otps(user, purpose: str) -> int:
    now = timezone.now()
    return CustomerAuthOTP.objects.filter(
        user=user,
        purpose=purpose,
        consumed_at__isnull=True,
        expires_at__gt=now,
    ).update(consumed_at=now)


def _issues_in_last_hour(user, purpose: str) -> int:
    since = timezone.now() - timedelta(hours=1)
    return CustomerAuthOTP.objects.filter(
        user=user,
        purpose=purpose,
        created_at__gte=since,
    ).count()


def issue_otp(user, purpose: str, *, force_new: bool = False) -> IssueResult:
    """
    Issue or reuse an OTP for (user, purpose).

    - Within cooldown with an active OTP: reuse (no new row, no plaintext).
    - Over hourly cap: rate_limited.
    - Otherwise: invalidate prior actives, create hashed row, return plaintext once.
    """
    now = timezone.now()
    cooldown = timedelta(seconds=_cooldown_seconds())
    active = get_active_otp(user, purpose)

    if not force_new and active is not None and (now - active.created_at) < cooldown:
        return IssueResult(status=IssueStatus.REUSED, record=active)

    if _issues_in_last_hour(user, purpose) >= _max_issues_per_hour():
        return IssueResult(status=IssueStatus.RATE_LIMITED, record=active)

    plaintext = generate_otp_code()
    code_hash = hash_otp_code(plaintext)
    max_attempts = _max_attempts()
    expires_at = now + timedelta(seconds=_ttl_seconds())

    with transaction.atomic():
        invalidate_active_otps(user, purpose)
        record = CustomerAuthOTP.objects.create(
            user=user,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
        )

    return IssueResult(status=IssueStatus.ISSUED, plaintext_otp=plaintext, record=record)


def _load_candidate(user, purpose: str) -> CustomerAuthOTP | None:
    return (
        CustomerAuthOTP.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True)
        .order_by('-created_at')
        .first()
    )


def verify_otp(user, purpose: str, code: str, *, consume: bool = False) -> CustomerAuthOTP:
    """
    Verify an OTP. Does not consume unless consume=True.
    Always re-checks hash, expiry, and attempt limits (confirm must call this independently).
    """
    normalized = (code or '').strip()
    record = _load_candidate(user, purpose)
    if record is None:
        raise AuthOTPError(OTP_INVALID_MESSAGE)

    now = timezone.now()
    if record.expires_at <= now:
        raise AuthOTPError(OTP_EXPIRED_MESSAGE)

    if record.attempt_count >= record.max_attempts:
        raise AuthOTPError(OTP_INVALID_MESSAGE)

    if not codes_match(normalized, record.code_hash):
        CustomerAuthOTP.objects.filter(pk=record.pk).update(
            attempt_count=record.attempt_count + 1
        )
        record.refresh_from_db(fields=['attempt_count'])
        raise AuthOTPError(OTP_INVALID_MESSAGE)

    if consume:
        record.consumed_at = now
        record.save(update_fields=['consumed_at'])

    return record


def consume_otp(user, purpose: str, code: str) -> CustomerAuthOTP:
    return verify_otp(user, purpose, code, consume=True)
