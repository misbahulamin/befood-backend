"""Phone availability check before OTP send (bind vs login contexts)."""

from __future__ import annotations

from user_management.models import CustomerProfile
from user_management.services.identity_normalization import (
    PhoneNormalizationError,
    normalize_phone_number,
)
from user_management.services.phone_otp import PHONE_CONFLICT_MESSAGE, PhoneOtpError

CONTEXT_BIND = 'bind'
CONTEXT_LOGIN = 'login'
REASON_PHONE_ALREADY_REGISTERED = 'PHONE_ALREADY_REGISTERED'


class PhoneAvailabilityError(Exception):
    def __init__(self, message: str, code: str = 'PHONE_AVAILABILITY_ERROR'):
        self.message = message
        self.code = code
        super().__init__(message)


def check_phone_availability(
    raw_phone: str,
    *,
    context: str,
    user=None,
) -> dict:
    """
    Normalize phone and report whether OTP/verification is allowed for ``context``.

    Never sends SMS.
    """
    context = (context or '').strip().lower()
    if context not in (CONTEXT_BIND, CONTEXT_LOGIN):
        raise PhoneAvailabilityError('Invalid context. Use "bind" or "login".', code='INVALID_CONTEXT')

    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError as exc:
        detail = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
        raise PhoneAvailabilityError(str(detail), code='INVALID_PHONE') from exc

    owner = (
        CustomerProfile.objects.select_related('user')
        .filter(phone=phone)
        .first()
    )
    phone_exists = owner is not None

    if context == CONTEXT_LOGIN:
        return {
            'phone': phone,
            'phone_exists': phone_exists,
            'available': True,
            'verification_allowed': True,
        }

    # bind
    if owner is None:
        return {
            'phone': phone,
            'phone_exists': False,
            'available': True,
            'verification_allowed': True,
        }
    if user is not None and owner.user_id == user.id:
        return {
            'phone': phone,
            'phone_exists': True,
            'available': True,
            'verification_allowed': True,
        }
    return {
        'phone': phone,
        'phone_exists': True,
        'available': False,
        'verification_allowed': False,
        'reason': REASON_PHONE_ALREADY_REGISTERED,
    }


def assert_phone_available_for_bind(user, raw_phone: str) -> str:
    """
    Raise PhoneOtpError(PHONE_CONFLICT) if another customer owns the phone.

    Returns normalized phone when bind is allowed. Does not send SMS.
    """
    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError as exc:
        detail = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
        raise PhoneOtpError(str(detail)) from exc

    owner = (
        CustomerProfile.objects.select_related('user')
        .filter(phone=phone)
        .first()
    )
    if owner is not None and owner.user_id != user.id:
        raise PhoneOtpError(PHONE_CONFLICT_MESSAGE, code='PHONE_CONFLICT')
    return phone
