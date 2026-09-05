"""Set primary email on phone-only (blank-email) customer accounts."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from user_management.services.identity_normalization import normalize_email
from user_management.services.pending_registration import email_owned_by_verified_customer


class CustomerEmailError(Exception):
    """Domain error for customer email set."""

    def __init__(self, message: str, *, code: str = 'invalid'):
        super().__init__(message)
        self.message = message
        self.code = code


@transaction.atomic
def set_customer_email_if_blank(user: User, raw_email: str) -> str:
    """
    Set User.email when it is currently blank (phone-only accounts).

    Does not mark email verified — verification remains a separate flow.
    Raises CustomerEmailError on conflict / already-set / invalid.
    """
    email = normalize_email(raw_email or '')
    if not email:
        raise CustomerEmailError('Enter a valid email address.', code='invalid')

    current = (user.email or '').strip()
    if current:
        raise CustomerEmailError('Email is already set on this account.', code='already_set')

    if email_owned_by_verified_customer(email):
        raise CustomerEmailError('This email is already used.', code='email_taken')

    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise CustomerEmailError('This email is already used.', code='email_taken')

    user.email = email
    user.save(update_fields=['email'])
    return email
