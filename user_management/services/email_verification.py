from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone

from .email_branding import build_activation_frontend_link, build_brand_email_context


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


def send_activation_email(request, user):
    activation_link, _, _ = build_activation_link(request, user)
    context = build_brand_email_context(
        user,
        extra={'activation_link': activation_link},
    )
    subject = render_to_string('emails/customer_activation_subject.txt', context).strip()
    text_body = render_to_string('emails/customer_activation_email.txt', context)
    html_body = render_to_string('emails/customer_activation_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def get_user_from_uid(uidb64):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
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
