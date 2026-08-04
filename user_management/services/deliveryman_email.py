from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .email_verification import generate_token, generate_uid, verify_token


PENDING_APPROVAL_MESSAGE = (
    'Your information has not been approved by admin yet. '
    'Please wait until your account verification is completed.'
)


def build_deliveryman_activation_link(request, user):
    uidb64 = generate_uid(user)
    token = generate_token(user)
    path = reverse(
        'user_management:deliveryman-verify-email',
        kwargs={'uidb64': uidb64, 'token': token},
    )
    return request.build_absolute_uri(path), uidb64, token


def send_deliveryman_activation_email(request, user):
    activation_link, _, _ = build_deliveryman_activation_link(request, user)
    context = {
        'user': user,
        'first_name': user.first_name,
        'brand_name': 'Befood-Bachelors E-Food',
        'activation_link': activation_link,
        'frontend_url': getattr(settings, 'FRONTEND_URL', ''),
    }
    subject = render_to_string('emails/deliveryman_activation_subject.txt', context).strip()
    text_body = render_to_string('emails/deliveryman_activation_email.txt', context)
    html_body = render_to_string('emails/deliveryman_activation_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def mark_deliveryman_email_verified(profile):
    """Mark email verified without enabling login (admin approval still required)."""
    profile.is_email_verified = True
    profile.email_verified_at = timezone.now()
    profile.save(update_fields=['is_email_verified', 'email_verified_at', 'updated_at'])


def send_deliveryman_approval_email(user):
    context = {
        'user': user,
        'first_name': user.first_name,
        'brand_name': 'Befood-Bachelors E-Food',
        'frontend_url': getattr(settings, 'FRONTEND_URL', ''),
    }
    subject = render_to_string('emails/deliveryman_approval_subject.txt', context).strip()
    text_body = render_to_string('emails/deliveryman_approval_email.txt', context)
    html_body = render_to_string('emails/deliveryman_approval_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def send_deliveryman_rejection_email(user, reason=''):
    context = {
        'user': user,
        'first_name': user.first_name,
        'brand_name': 'Befood-Bachelors E-Food',
        'reason': reason or '',
        'frontend_url': getattr(settings, 'FRONTEND_URL', ''),
    }
    subject = render_to_string('emails/deliveryman_rejection_subject.txt', context).strip()
    text_body = render_to_string('emails/deliveryman_rejection_email.txt', context)
    html_body = render_to_string('emails/deliveryman_rejection_email.html', context)
    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


def verify_deliveryman_token(user, token):
    return verify_token(user, token)
