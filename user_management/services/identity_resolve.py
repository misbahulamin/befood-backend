"""Resolve existing customers by email and/or phone (no creation)."""

from __future__ import annotations

from user_management.models import CustomerProfile
from user_management.services.identity_normalization import (
    PhoneNormalizationError,
    normalize_email,
    normalize_phone_number,
)


def find_customer_by_phone(raw_phone: str | None) -> CustomerProfile | None:
    """Return the customer owning the normalized phone, if any."""
    if raw_phone is None or str(raw_phone).strip() == '':
        return None
    try:
        phone = normalize_phone_number(raw_phone)
    except PhoneNormalizationError:
        return None
    return (
        CustomerProfile.objects.select_related('user')
        .filter(phone=phone)
        .first()
    )


def find_customer_by_email(raw_email: str | None) -> CustomerProfile | None:
    """Return a customer profile whose User.email matches (case-insensitive)."""
    if raw_email is None or str(raw_email).strip() == '':
        return None
    email = normalize_email(raw_email)
    if not email:
        return None
    return (
        CustomerProfile.objects.select_related('user')
        .filter(user__email__iexact=email)
        .first()
    )


def resolve_customer(
    *,
    email: str | None = None,
    phone: str | None = None,
) -> CustomerProfile | None:
    """
    Resolve an existing customer by phone first, then email.

    Does not create accounts. Used by create-path guards.
    """
    by_phone = find_customer_by_phone(phone)
    if by_phone is not None:
        return by_phone
    return find_customer_by_email(email)
