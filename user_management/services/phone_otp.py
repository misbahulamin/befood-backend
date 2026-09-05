"""Phone OTP issue and verify services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from user_management.models import CustomerProfile, PhoneAuthOTP
from user_management.services.auth_otp import generate_otp_code, hash_otp_code, codes_match
from user_management.services.auth_session import build_customer_auth_response
from user_management.services.customer_factory import create_phone_only_customer
from user_management.services.identity_normalization import (
    PhoneNormalizationError,
    normalize_phone_number,
)
from user_management.services.sms_net_bd import SmsNetBdError, send_otp_sms

OTP_INVALID_MESSAGE = 'Invalid or expired OTP.'
OTP_EXPIRED_MESSAGE = 'OTP expired.'
OTP_RATE_LIMITED_MESSAGE = 'Too many OTP requests. Please try again later.'
OTP_COOLDOWN_MESSAGE = 'Please wait before requesting another OTP.'
PHONE_CONFLICT_MESSAGE = 'This phone number is already linked to another account.'


class PhoneOtpIssueStatus(str, Enum):
    ISSUED = 'issued'
    RATE_LIMITED = 'rate_limited'
    COOLDOWN = 'cooldown'


@dataclass(frozen=True)
class PhoneOtpIssueResult:
    status: PhoneOtpIssueStatus
    phone: str | None = None
    record: PhoneAuthOTP | None = None


class PhoneOtpError(Exception):
    def __init__(self, message: str, code: str = 'PHONE_OTP_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def _ttl_seconds() -> int:
    return int(getattr(settings, 'PHONE_OTP_TTL_SECONDS', 600))


def _max_attempts() -> int:
    return int(getattr(settings, 'PHONE_OTP_MAX_ATTEMPTS', 5))


def _cooldown_seconds() -> int:
    return int(getattr(settings, 'PHONE_OTP_RESEND_COOLDOWN_SECONDS', 60))


def _max_issues_per_hour() -> int:
    return int(getattr(settings, 'PHONE_OTP_MAX_ISSUES_PER_HOUR', 10))


def _get_active_otp(phone: str) -> PhoneAuthOTP | None:
    now = timezone.now()
    return (
        PhoneAuthOTP.objects.filter(
            phone=phone,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by('-created_at')
        .first()
    )


def _issues_in_last_hour(phone: str) -> int:
    since = timezone.now() - timedelta(hours=1)
    return PhoneAuthOTP.objects.filter(phone=phone, created_at__gte=since).count()


def _invalidate_active(phone: str) -> None:
    now = timezone.now()
    PhoneAuthOTP.objects.filter(
        phone=phone,
        consumed_at__isnull=True,
        expires_at__gt=now,
    ).update(consumed_at=now)


def issue_phone_otp(raw_phone: str) -> PhoneOtpIssueResult:
    """
    Normalize phone, enforce rate limits, hash+store OTP, send SMS.

    On SMS failure the OTP row is consumed so it cannot be used without delivery.
    """
    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError as exc:
        raise PhoneOtpError(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)) from exc

    now = timezone.now()
    active = _get_active_otp(phone)
    if active is not None and (now - active.created_at) < timedelta(seconds=_cooldown_seconds()):
        return PhoneOtpIssueResult(status=PhoneOtpIssueStatus.COOLDOWN, phone=phone, record=active)

    if _issues_in_last_hour(phone) >= _max_issues_per_hour():
        return PhoneOtpIssueResult(status=PhoneOtpIssueStatus.RATE_LIMITED, phone=phone, record=active)

    plaintext = generate_otp_code()
    code_hash = hash_otp_code(plaintext)
    expires_at = now + timedelta(seconds=_ttl_seconds())

    with transaction.atomic():
        _invalidate_active(phone)
        record = PhoneAuthOTP.objects.create(
            phone=phone,
            code_hash=code_hash,
            expires_at=expires_at,
            max_attempts=_max_attempts(),
            issue_window_started_at=now,
            issues_in_window=1,
        )

    try:
        send_otp_sms(phone, plaintext)
    except SmsNetBdError as exc:
        record.consumed_at = timezone.now()
        record.save(update_fields=['consumed_at'])
        raise PhoneOtpError(exc.message, code=exc.code) from exc

    return PhoneOtpIssueResult(status=PhoneOtpIssueStatus.ISSUED, phone=phone, record=record)


def _load_candidate(phone: str) -> PhoneAuthOTP | None:
    return (
        PhoneAuthOTP.objects.filter(phone=phone, consumed_at__isnull=True)
        .order_by('-created_at')
        .first()
    )


@transaction.atomic
def verify_phone_otp(
    raw_phone: str,
    code: str,
    *,
    device_token: str | None = None,
    platform: str | None = None,
    user_agent: str = '',
) -> dict:
    """Verify OTP and create-or-login customer; returns unified auth envelope."""
    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError as exc:
        raise PhoneOtpError(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)) from exc

    normalized_code = (code or '').strip()
    _consume_valid_otp(phone, normalized_code)
    now = timezone.now()

    profile = (
        CustomerProfile.objects.select_related('user')
        .filter(phone=phone)
        .first()
    )
    if profile is None:
        user, profile = create_phone_only_customer(phone)
    else:
        user = profile.user
        if not profile.is_phone_verified:
            profile.is_phone_verified = True
            profile.phone_verified_at = now
            profile.save(update_fields=['is_phone_verified', 'phone_verified_at', 'updated_at'])

    return build_customer_auth_response(
        user,
        auth_provider='phone',
        device_token=device_token,
        platform=platform,
        user_agent=user_agent,
    )


def _consume_valid_otp(phone: str, normalized_code: str) -> None:
    """Validate and consume an OTP for ``phone`` or raise PhoneOtpError."""
    record = _load_candidate(phone)
    if record is None:
        raise PhoneOtpError(OTP_INVALID_MESSAGE)

    now = timezone.now()
    if record.expires_at <= now:
        raise PhoneOtpError(OTP_EXPIRED_MESSAGE)

    if record.attempt_count >= record.max_attempts:
        raise PhoneOtpError(OTP_INVALID_MESSAGE)

    if not codes_match(normalized_code, record.code_hash):
        PhoneAuthOTP.objects.filter(pk=record.pk).update(attempt_count=record.attempt_count + 1)
        raise PhoneOtpError(OTP_INVALID_MESSAGE)

    record.consumed_at = now
    record.save(update_fields=['consumed_at'])


@transaction.atomic
def bind_phone_otp_to_user(
    user,
    raw_phone: str,
    code: str,
    *,
    device_token: str | None = None,
    platform: str | None = None,
    user_agent: str = '',
) -> dict:
    """
    Attach a verified phone to the authenticated customer (no new User).

    Raises PhoneOtpError with code PHONE_CONFLICT when the phone belongs to another customer.
    """
    if not hasattr(user, 'customer_profile'):
        raise PhoneOtpError('Customer profile not found for this account.')

    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError as exc:
        raise PhoneOtpError(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail)) from exc

    profile = user.customer_profile
    now = timezone.now()

    owner = (
        CustomerProfile.objects.select_related('user')
        .filter(phone=phone)
        .first()
    )
    if owner is not None and owner.user_id != user.id:
        raise PhoneOtpError(PHONE_CONFLICT_MESSAGE, code='PHONE_CONFLICT')

    if profile.is_phone_verified and profile.phone == phone:
        return build_customer_auth_response(
            user,
            auth_provider='phone',
            device_token=device_token,
            platform=platform,
            user_agent=user_agent,
        )

    _consume_valid_otp(phone, (code or '').strip())

    profile.phone = phone
    profile.is_phone_verified = True
    profile.phone_verified_at = now
    profile.save(
        update_fields=['phone', 'is_phone_verified', 'phone_verified_at', 'updated_at']
    )

    return build_customer_auth_response(
        user,
        auth_provider='phone',
        device_token=device_token,
        platform=platform,
        user_agent=user_agent,
    )
