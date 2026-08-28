"""Customer password-reset email helpers (separate from activation tokens)."""

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .email_branding import build_brand_email_context, build_password_reset_link

password_reset_token_generator = PasswordResetTokenGenerator()

PASSWORD_RESET_REQUEST_MESSAGE = (
    'If an account exists for this email, password reset instructions will be sent.'
)


def generate_password_reset_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def generate_password_reset_token(user):
    return password_reset_token_generator.make_token(user)


def send_password_reset_email(user):
    uidb64 = generate_password_reset_uid(user)
    token = generate_password_reset_token(user)
    reset_link = build_password_reset_link(uidb64, token)
    context = build_brand_email_context(
        user,
        extra={
            'reset_link': reset_link,
            'uidb64': uidb64,
            'token': token,
        },
    )
    subject = render_to_string('emails/customer_password_reset_subject.txt', context).strip()
    text_body = render_to_string('emails/customer_password_reset_email.txt', context)
    html_body = render_to_string('emails/customer_password_reset_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)
    return reset_link


def request_password_reset(email):
    """
    Trigger password-reset mail when a customer account exists.

    Always returns the same generic message for anti-enumeration.
    """
    normalized = (email or '').strip().lower()
    user = User.objects.filter(email__iexact=normalized).first()
    if user and hasattr(user, 'customer_profile'):
        send_password_reset_email(user)
    return PASSWORD_RESET_REQUEST_MESSAGE
