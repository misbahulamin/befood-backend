from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone

from .auth_otp import (
    AuthOTPError,
    IssueStatus,
    PURPOSE_EMAIL_VERIFICATION,
    consume_otp,
    issue_otp,
)
from .email_branding import build_activation_frontend_link, build_brand_email_context
from .pending_registration import (
    EMAIL_ALREADY_VERIFIED_MESSAGE,
    EMAIL_OTP_INVALID_MESSAGE,
    EMAIL_VERIFIED_SUCCESS_MESSAGE,
    email_owned_by_verified_customer,
    get_active_pending,
    resend_pending_verification,
    send_pending_activation_email,
    verify_pending_email_with_link,
    verify_pending_email_with_otp,
)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.password}{user.last_login}{timestamp}{user.is_active}'


token_generator = EmailVerificationTokenGenerator()
TOKEN_EXPIRY_SECONDS = 24 * 60 * 60
DjangoEpoch = datetime(2001, 1, 1, tzinfo=dt_timezone.utc)


def generate_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def generate_token(user):
    return token_generator.make_token(user)


def build_activation_link(request, user):
    """Build SPA activation URL from FRONTEND_URL (request host is ignored)."""
    uidb64 = generate_uid(user)
    token = generate_token(user)
    return build_activation_frontend_link(uidb64, token), uidb64, token


def send_activation_email(request, user, *, force_new_otp: bool = False):
    """
    Send branded activation email with link + OTP when a new OTP is issued.

    Legacy path for existing inactive unverified User rows.
    Returns IssueStatus (issued / reused / rate_limited). When reused or
    rate_limited, no email is sent (cooldown / hourly protection).
    """
    issue = issue_otp(user, PURPOSE_EMAIL_VERIFICATION, force_new=force_new_otp)
    if issue.status != IssueStatus.ISSUED:
        return issue.status

    activation_link, _, _ = build_activation_link(request, user)
    context = build_brand_email_context(
        user,
        extra={
            'activation_link': activation_link,
            'otp_code': issue.plaintext_otp,
            'otp_ttl_minutes': int(getattr(settings, 'AUTH_OTP_TTL_SECONDS', 600)) // 60,
        },
    )
    subject = render_to_string('emails/customer_activation_subject.txt', context).strip()
    text_body = render_to_string('emails/customer_activation_email.txt', context)
    html_body = render_to_string('emails/customer_activation_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
    return issue.status


def get_user_from_uid(uidb64):
    try:
        raw = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        return None
    if raw.startswith('pending:'):
        return None
    try:
        return User.objects.get(pk=raw)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def token_is_expired(token):
    try:
        ts_b36 = token.split('-')[0]
        ts = base36_to_int(ts_b36)
    except Exception:
        return True
    return timezone.now() > (DjangoEpoch + timedelta(seconds=ts + TOKEN_EXPIRY_SECONDS))


def verify_token(user, token):
    return user is not None and not token_is_expired(token) and token_generator.check_token(user, token)


def mark_email_verified(profile):
    profile.is_email_verified = True
    profile.email_verified_at = timezone.now()
    profile.user.is_active = True
    profile.user.save(update_fields=['is_active'])
    profile.save(update_fields=['is_email_verified', 'email_verified_at', 'updated_at'])


def verify_email_with_otp(email: str, otp: str) -> str:
    """
    Verify customer email using OTP.

    Prefers pending registration (no User yet). Falls back to legacy
    inactive unverified User + CustomerAuthOTP rows.
    """
    normalized = (email or '').strip().lower()

    if email_owned_by_verified_customer(normalized):
        return EMAIL_ALREADY_VERIFIED_MESSAGE

    pending = get_active_pending(normalized)
    if pending is not None:
        return verify_pending_email_with_otp(normalized, otp)

    user = User.objects.filter(email__iexact=normalized).first()
    if not user or not hasattr(user, 'customer_profile'):
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE)

    profile = user.customer_profile
    if profile.is_email_verified:
        return EMAIL_ALREADY_VERIFIED_MESSAGE

    try:
        consume_otp(user, PURPOSE_EMAIL_VERIFICATION, otp)
    except AuthOTPError as exc:
        if exc.message == 'OTP expired.':
            raise
        raise AuthOTPError(EMAIL_OTP_INVALID_MESSAGE) from exc

    mark_email_verified(profile)
    return EMAIL_VERIFIED_SUCCESS_MESSAGE


def verify_email_link(uidb64: str, token: str) -> tuple[dict, int]:
    """
    Dual-path link verification: pending registration first, then legacy User.

    Returns (response_body, http_status).
    """
    message, status_code = verify_pending_email_with_link(uidb64, token)
    if status_code == 200:
        return {'message': message}, 200
    if message == '' and status_code == 400:
        # Not a valid pending link — try legacy user path.
        pass
    elif status_code == 400:
        return {'detail': 'Invalid or expired verification link.'}, 400

    user = get_user_from_uid(uidb64)
    if not user:
        return {'detail': 'Invalid or expired verification link.'}, 400
    if hasattr(user, 'customer_profile') and user.customer_profile.is_email_verified:
        return {'message': 'Email is already verified.'}, 200
    if not verify_token(user, token):
        return {'detail': 'Invalid or expired verification link.'}, 400
    mark_email_verified(user.customer_profile)
    return {'message': EMAIL_VERIFIED_SUCCESS_MESSAGE}, 200


def resend_verification_email(request, email: str) -> dict:
    """Resend for pending registrations, with legacy User fallback."""
    normalized = (email or '').strip().lower()
    if email_owned_by_verified_customer(normalized):
        return {'message': 'This email is already verified.'}

    pending = get_active_pending(normalized)
    if pending is not None:
        send_pending_activation_email(request, pending)
        return {'message': 'Verification email has been sent again.'}

    user = User.objects.filter(email__iexact=normalized).first()
    if not user or not hasattr(user, 'customer_profile'):
        return {'message': 'If the account exists, verification instructions will be sent.'}
    if user.customer_profile.is_email_verified:
        return {'message': 'This email is already verified.'}
    send_activation_email(request, user)
    return {'message': 'Verification email has been sent again.'}


# Re-export for callers that imported these names previously via this module.
__all__ = [
    'EMAIL_VERIFIED_SUCCESS_MESSAGE',
    'EMAIL_OTP_INVALID_MESSAGE',
    'build_activation_link',
    'generate_token',
    'generate_uid',
    'get_user_from_uid',
    'mark_email_verified',
    'resend_pending_verification',
    'resend_verification_email',
    'send_activation_email',
    'send_pending_activation_email',
    'token_is_expired',
    'verify_email_link',
    'verify_email_with_otp',
    'verify_token',
]
