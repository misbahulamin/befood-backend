"""Customer password-reset helpers (separate from activation tokens)."""

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.authtoken.models import Token

from .auth_otp import (
    AuthOTPError,
    IssueStatus,
    PURPOSE_PASSWORD_RESET,
    consume_otp,
    issue_otp,
    verify_otp,
)
from .email_branding import build_brand_email_context, build_password_reset_link

password_reset_token_generator = PasswordResetTokenGenerator()

PASSWORD_RESET_REQUEST_MESSAGE = (
    'If an account exists for this email, password reset instructions will be sent.'
)
PASSWORD_RESET_VALIDATE_SUCCESS_MESSAGE = 'Password reset link is valid.'
PASSWORD_RESET_CONFIRM_SUCCESS_MESSAGE = (
    'Password has been reset successfully. You can now login.'
)
PASSWORD_RESET_INVALID_TOKEN_MESSAGE = 'Invalid or expired password reset link.'
PASSWORD_RESET_OTP_VALID_MESSAGE = 'OTP verified successfully.'
PASSWORD_RESET_OTP_CONFIRM_SUCCESS_MESSAGE = 'Password reset successfully.'
PASSWORD_RESET_OTP_INVALID_MESSAGE = 'Invalid or expired OTP.'


class PasswordResetError(Exception):
    """Raised when password-reset validate/confirm cannot proceed."""


def generate_password_reset_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def generate_password_reset_token(user):
    return password_reset_token_generator.make_token(user)


def get_customer_user_from_uid(uidb64):
    """
    Resolve a customer User from uidb64.

    Returns None for malformed uids, missing users, or users without customer_profile.
    """
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not hasattr(user, 'customer_profile'):
        return None
    return user


def get_customer_user_by_email(email):
    normalized = (email or '').strip().lower()
    user = User.objects.filter(email__iexact=normalized).first()
    if user and hasattr(user, 'customer_profile'):
        return user
    return None


def check_password_reset_token(user, token):
    return (
        user is not None
        and bool(token)
        and password_reset_token_generator.check_token(user, token)
    )


def send_password_reset_email(user, *, force_new_otp: bool = False):
    """
    Send branded reset email with link + OTP when a new OTP is issued.

    Returns IssueStatus. When reused or rate_limited, no email is sent.
    """
    issue = issue_otp(user, PURPOSE_PASSWORD_RESET, force_new=force_new_otp)
    if issue.status != IssueStatus.ISSUED:
        return issue.status

    uidb64 = generate_password_reset_uid(user)
    token = generate_password_reset_token(user)
    reset_link = build_password_reset_link(uidb64, token)
    context = build_brand_email_context(
        user,
        extra={
            'reset_link': reset_link,
            'uidb64': uidb64,
            'token': token,
            'otp_code': issue.plaintext_otp,
            'otp_ttl_minutes': int(getattr(settings, 'AUTH_OTP_TTL_SECONDS', 600)) // 60,
        },
    )
    subject = render_to_string('emails/customer_password_reset_subject.txt', context).strip()
    text_body = render_to_string('emails/customer_password_reset_email.txt', context)
    html_body = render_to_string('emails/customer_password_reset_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
    return issue.status


def request_password_reset(email):
    """
    Trigger password-reset mail when a customer account exists.

    Always returns the same generic message for anti-enumeration.
    Cooldown / hourly caps may skip sending without changing the message.
    """
    user = get_customer_user_by_email(email)
    if user:
        send_password_reset_email(user)
    return PASSWORD_RESET_REQUEST_MESSAGE


def validate_password_reset(uidb64, token):
    """
    Check that uid+token form a valid customer password-reset link.

    Does not change the password. Raises PasswordResetError when invalid.
    """
    user = get_customer_user_from_uid(uidb64)
    if not check_password_reset_token(user, token):
        raise PasswordResetError(PASSWORD_RESET_INVALID_TOKEN_MESSAGE)
    return PASSWORD_RESET_VALIDATE_SUCCESS_MESSAGE


def confirm_password_reset(uidb64, token, new_password):
    """
    Set a new password for a customer after validating the reset token.

    Invalidates outstanding reset tokens (via password hash change) and deletes
    all DRF auth tokens for the user. Raises PasswordResetError when the link
    is invalid. Password strength must already be validated by the caller
    (serializer); this also re-validates against the resolved user.
    """
    user = get_customer_user_from_uid(uidb64)
    if not check_password_reset_token(user, token):
        raise PasswordResetError(PASSWORD_RESET_INVALID_TOKEN_MESSAGE)

    validate_password(new_password, user=user)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()

    return PASSWORD_RESET_CONFIRM_SUCCESS_MESSAGE


def validate_password_reset_otp(email: str, otp: str) -> str:
    """
    UX check that OTP is currently valid. Does NOT consume and does NOT grant
    password-reset authority — confirm_password_reset_otp must re-verify.
    """
    user = get_customer_user_by_email(email)
    if not user:
        raise AuthOTPError(PASSWORD_RESET_OTP_INVALID_MESSAGE)
    try:
        verify_otp(user, PURPOSE_PASSWORD_RESET, otp, consume=False)
    except AuthOTPError as exc:
        if exc.message == 'OTP expired.':
            raise
        raise AuthOTPError(PASSWORD_RESET_OTP_INVALID_MESSAGE) from exc
    return PASSWORD_RESET_OTP_VALID_MESSAGE


def confirm_password_reset_otp(email: str, otp: str, new_password: str) -> str:
    """
    Independently re-verify OTP, set password, consume OTP, wipe DRF tokens.
    """
    user = get_customer_user_by_email(email)
    if not user:
        raise AuthOTPError(PASSWORD_RESET_OTP_INVALID_MESSAGE)

    validate_password(new_password, user=user)

    with transaction.atomic():
        try:
            consume_otp(user, PURPOSE_PASSWORD_RESET, otp)
        except AuthOTPError as exc:
            if exc.message == 'OTP expired.':
                raise
            raise AuthOTPError(PASSWORD_RESET_OTP_INVALID_MESSAGE) from exc
        user.set_password(new_password)
        user.save(update_fields=['password'])
        Token.objects.filter(user=user).delete()

    return PASSWORD_RESET_OTP_CONFIRM_SUCCESS_MESSAGE
