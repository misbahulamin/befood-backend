"""Email-first lookup for unified customer auth UX (no User creation)."""

from __future__ import annotations

from django.contrib.auth.models import User

from user_management.services.identity_normalization import normalize_email
from user_management.services.pending_registration import (
    email_owned_by_verified_customer,
    get_active_pending,
)

STATUS_EXISTS = 'exists'
STATUS_PENDING = 'pending'
STATUS_AVAILABLE = 'available'


def check_customer_email(raw_email: str) -> dict:
    """
    Normalize email and return branch status for the client.

    Does not create users, issue tokens, or return password material.
    Credential flags (has_password / password_setup_required) are attached only
    when status is verified ``exists``.
    """
    email = normalize_email(raw_email)
    if email_owned_by_verified_customer(email):
        user = User.objects.filter(email__iexact=email).first()
        has_password = bool(user and user.has_usable_password())
        return {
            'email': email,
            'status': STATUS_EXISTS,
            'has_password': has_password,
            'password_setup_required': not has_password,
        }
    if get_active_pending(email) is not None:
        return {'email': email, 'status': STATUS_PENDING}
    return {'email': email, 'status': STATUS_AVAILABLE}
