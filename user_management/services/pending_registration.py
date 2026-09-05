"""Pending customer registration: OTP, link tokens, and account finalization."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, User
from django.core.mail import EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import ValidationError

from user_management.models import CustomerProfile, PendingCustomerRegistration
from user_management.services.auth_otp import (
    AuthOTPError,
    IssueResult,
    IssueStatus,
    OTP_EXPIRED_MESSAGE,
    codes_match,
    generate_otp_code,
    hash_otp_code,
)
from user_management.services.email_branding import (
    build_activation_frontend_link,
    build_brand_email_context,
)
from user_management.services.identity_normalization import normalize_email

PENDING_UID_PREFIX = 'pending:'
PENDING_SIGNER_SALT = 'pending-customer-email-verify'
LINK_MAX_AGE_SECONDS = 24 * 60 * 60
EMAIL_VERIFIED_SUCCESS_MESSAGE = 'Email verified successfully. You can now login.'
EMAIL_OTP_INVALID_MESSAGE = 'Invalid or expired OTP.'
EMAIL_ALREADY_VERIFIED_MESSAGE = 'Email is already verified.'


def _ttl_seconds() -> int:
    return int(getattr(settings, 'AUTH_OTP_TTL_SECONDS', 600))


def _max_attempts() -> int:
    return int(getattr(settings, 'AUTH_OTP_MAX_ATTEMPTS', 5))


def _cooldown_seconds() -> int:
    return int(getattr(settings, 'AUTH_OTP_RESEND_COOLDOWN_SECONDS', 60))


def _max_issues_per_hour() -> int:
    return int(getattr(settings, 'AUTH_OTP_MAX_ISSUES_PER_HOUR', 10))


def _pending_lifetime_seconds() -> int:
    return int(getattr(settings, 'PENDING_REGISTRATION_LIFETIME_SECONDS', LINK_MAX_AGE_SECONDS))


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=PENDING_SIGNER_SALT)


def pending_lifetime_expires_at():
    return timezone.now() + timedelta(seconds=_pending_lifetime_seconds())


def get_active_pending(email: str) -> PendingCustomerRegistration | None:
    normalized = normalize_email(email)
    now = timezone.now()
    return (
        PendingCustomerRegistration.objects.filter(email__iexact=normalized, expires_at__gt=now)
        .order_by('-created_at')
        .first()
    )


def email_owned_by_verified_customer(email: str) -> bool:
    normalized = normalize_email(email)
    return CustomerProfile.objects.filter(
        user__email__iexact=normalized,
        is_email_verified=True,
    ).exists()


def delete_legacy_unverified_customer(email: str) -> bool:
    """Remove inactive unverified customer User so signup can become pending-only."""
    normalized = normalize_email(email)
    user = (
        User.objects.filter(email__iexact=normalized, customer_profile__isnull=False)
        .select_related('customer_profile')
        .first()
    )
    if user is None:
        return False
    profile = user.customer_profile
    if profile.is_email_verified:
        return False
    user.delete()
    return True


def upsert_pending_registration(validated_data) -> PendingCustomerRegistration:
    email = normalize_email(validated_data['email'])
    if email_owned_by_verified_customer(email):
        raise ValidationError({'email': ['Email already exists.']})

    delete_legacy_unverified_customer(email)

    password = validated_data['password']
    password_hash = make_password(password)
    defaults = {
        'password_hash': password_hash,
        'first_name': validated_data.get('first_name') or '',
        'last_name': validated_data.get('last_name') or '',
        'phone': validated_data.get('phone'),
        'occupation': validated_data.get('occupation'),
        'is_bachelor': validated_data.get('is_bachelor'),
        'expires_at': pending_lifetime_expires_at(),
    }
    pending, _created = PendingCustomerRegistration.objects.update_or_create(
        email=email,
        defaults=defaults,
    )
    return pending


def issue_pending_otp(
    pending: PendingCustomerRegistration,
    *,
    force_new: bool = False,
) -> IssueResult:
    now = timezone.now()
    cooldown = timedelta(seconds=_cooldown_seconds())
    has_active = (
        bool(pending.otp_code_hash)
        and pending.otp_expires_at is not None
        and pending.otp_expires_at > now
        and pending.otp_attempt_count < pending.otp_max_attempts
    )

    if (
        not force_new
        and has_active
        and pending.otp_created_at is not None
        and (now - pending.otp_created_at) < cooldown
    ):
        return IssueResult(status=IssueStatus.REUSED, plaintext_otp=None, record=None)

    window_start = pending.otp_window_started_at
    issue_count = pending.otp_issue_count
    if window_start is None or (now - window_start) >= timedelta(hours=1):
        window_start = now
        issue_count = 0

    if issue_count >= _max_issues_per_hour():
        return IssueResult(status=IssueStatus.RATE_LIMITED, plaintext_otp=None, record=None)

    plaintext = generate_otp_code()
    pending.otp_code_hash = hash_otp_code(plaintext)
    pending.otp_created_at = now
    pending.otp_expires_at = now + timedelta(seconds=_ttl_seconds())
    pending.otp_attempt_count = 0
    pending.otp_max_attempts = _max_attempts()
    pending.otp_issue_count = issue_count + 1
    pending.otp_window_started_at = window_start
    pending.expires_at = pending_lifetime_expires_at()
    pending.save(
        update_fields=[
            'otp_code_hash',
            'otp_created_at',
            'otp_expires_at',
            'otp_attempt_count',
            'otp_max_attempts',
            'otp_issue_count',
            'otp_window_started_at',
            'expires_at',
            'updated_at',
        ]
    )
    return IssueResult(status=IssueStatus.ISSUED, plaintext_otp=plaintext, record=None)


def verify_pending_otp(pending: PendingCustomerRegistration, code: str) -> None:
    normalized = (code or '').strip()
    if not pending.otp_code_hash or pending.otp_expires_at is None:
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)

    now = timezone.now()
    if pending.is_expired:
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)
    if pending.otp_expires_at <= now:
        raise AuthOTPError(OTP_EXPIRED_MESSAGE)
    if pending.otp_attempt_count >= pending.otp_max_attempts:
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)
    if not codes_match(normalized, pending.otp_code_hash):
        pending.otp_attempt_count += 1
        pending.save(update_fields=['otp_attempt_count', 'updated_at'])
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)


def encode_pending_uid(pending: PendingCustomerRegistration) -> str:
    return urlsafe_base64_encode(force_bytes(f'{PENDING_UID_PREFIX}{pending.pk}'))


def decode_pending_uid(uidb64: str) -> PendingCustomerRegistration | None:
    try:
        raw = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        return None
    if not raw.startswith(PENDING_UID_PREFIX):
        return None
    try:
        pk = int(raw[len(PENDING_UID_PREFIX) :])
    except (TypeError, ValueError):
        return None
    return PendingCustomerRegistration.objects.filter(pk=pk).first()


def _pending_link_fingerprint(pending: PendingCustomerRegistration) -> str:
    """Stable URL-safe fingerprint of the pending password (no '/' characters)."""
    import hashlib

    return hashlib.sha256(pending.password_hash.encode('utf-8')).hexdigest()[:32]


def generate_pending_link_token(pending: PendingCustomerRegistration) -> str:
    return _signer().sign(f'{pending.pk}:{pending.email}:{_pending_link_fingerprint(pending)}')


def verify_pending_link_token(pending: PendingCustomerRegistration, token: str) -> bool:
    if pending is None or pending.is_expired:
        return False
    try:
        value = _signer().unsign(token, max_age=LINK_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False
    expected = f'{pending.pk}:{pending.email}:{_pending_link_fingerprint(pending)}'
    return value == expected


def build_pending_activation_link(pending: PendingCustomerRegistration) -> tuple[str, str, str]:
    uidb64 = encode_pending_uid(pending)
    token = generate_pending_link_token(pending)
    return build_activation_frontend_link(uidb64, token), uidb64, token


def _pending_email_user_like(pending: PendingCustomerRegistration):
    return SimpleNamespace(
        email=pending.email,
        first_name=pending.first_name or '',
        customer_profile=None,
    )


def send_pending_activation_email(request, pending: PendingCustomerRegistration, *, force_new_otp: bool = False):
    """
    Send branded activation email for a pending registration.

    Returns IssueStatus. Email is sent only when a new OTP is issued.
    """
    issue = issue_pending_otp(pending, force_new=force_new_otp)
    if issue.status != IssueStatus.ISSUED:
        return issue.status

    pending.refresh_from_db()
    activation_link, _, _ = build_pending_activation_link(pending)
    context = build_brand_email_context(
        _pending_email_user_like(pending),
        extra={
            'activation_link': activation_link,
            'otp_code': issue.plaintext_otp,
            'otp_ttl_minutes': _ttl_seconds() // 60,
        },
    )
    subject = render_to_string('emails/customer_activation_subject.txt', context).strip()
    text_body = render_to_string('emails/customer_activation_email.txt', context)
    html_body = render_to_string('emails/customer_activation_email.html', context)
    email = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [pending.email],
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
    return issue.status


@transaction.atomic
def finalize_pending_registration(pending: PendingCustomerRegistration) -> User:
    """Create the real customer account from a pending row, then delete the pending row."""
    from user_management.services.auth_service import build_username

    pending = PendingCustomerRegistration.objects.select_for_update().get(pk=pending.pk)
    if pending.is_expired:
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)
    if email_owned_by_verified_customer(pending.email):
        pending.delete()
        raise AuthOTPError(EMAIL_ALREADY_VERIFIED_MESSAGE)

    # Clear any leftover unverified user for this email.
    delete_legacy_unverified_customer(pending.email)

    user = User(
        username=build_username(pending.email),
        email=pending.email,
        first_name=pending.first_name or '',
        last_name=pending.last_name or '',
        is_active=True,
    )
    user.password = pending.password_hash
    user.save()
    profile = CustomerProfile.objects.create(
        user=user,
        phone=pending.phone,
        occupation=pending.occupation,
        is_bachelor=pending.is_bachelor,
        is_email_verified=True,
        email_verified_at=timezone.now(),
    )
    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)
    pending.delete()
    # Touch profile for callers that expect it.
    _ = profile
    return user


def verify_pending_email_with_otp(email: str, otp: str) -> User:
    pending = get_active_pending(email)
    if pending is None:
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)
    try:
        verify_pending_otp(pending, otp)
    except AuthOTPError as exc:
        if exc.message == OTP_EXPIRED_MESSAGE:
            raise
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE) from exc
    return finalize_pending_registration(pending)


def verify_pending_email_with_link(uidb64: str, token: str) -> tuple[str, int, User | None]:
    """
    Verify pending registration via link.

    Returns (message, http_status_hint, user_or_none) where hint is 200 on success.
    """
    pending = decode_pending_uid(uidb64)
    if pending is None or not verify_pending_link_token(pending, token):
        return '', 400, None
    if email_owned_by_verified_customer(pending.email):
        pending.delete()
        return EMAIL_ALREADY_VERIFIED_MESSAGE, 200, None
    user = finalize_pending_registration(pending)
    return EMAIL_VERIFIED_SUCCESS_MESSAGE, 200, user


def resend_pending_verification(request, email: str) -> str:
    pending = get_active_pending(email)
    if pending is None:
        return 'If the account exists, verification instructions will be sent.'
    send_pending_activation_email(request, pending)
    return 'Verification email has been sent again.'


def cleanup_expired_pending_registrations() -> int:
    deleted, _ = PendingCustomerRegistration.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted


def migrate_legacy_unverified_to_pending(user: User) -> PendingCustomerRegistration | None:
    """
    Convert a legacy inactive unverified customer into a pending registration.

    Used by management command / ops cleanup. Does not send email.
    """
    profile = getattr(user, 'customer_profile', None)
    if profile is None or profile.is_email_verified:
        return None
    email = normalize_email(user.email)
    pending, _ = PendingCustomerRegistration.objects.update_or_create(
        email=email,
        defaults={
            'password_hash': user.password,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'phone': profile.phone,
            'occupation': profile.occupation,
            'is_bachelor': profile.is_bachelor,
            'expires_at': pending_lifetime_expires_at(),
        },
    )
    user.delete()
    return pending

