"""Resolve or create customers for social login with linking rules."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import ValidationError

from user_management.models import CustomerProfile, SocialIdentity
from user_management.services.customer_factory import create_social_customer
from user_management.services.identity_normalization import (
    PhoneNormalizationError,
    normalize_email,
    normalize_phone_number,
)


class SocialLinkConflict(Exception):
    """Provider identity already bound to a different user."""

    def __init__(self, message: str = 'This social account is already linked to another user.'):
        self.message = message
        super().__init__(message)


@transaction.atomic
def resolve_or_create_social_user(
    *,
    provider: str,
    provider_user_id: str,
    email: str = '',
    email_verified: bool = False,
    phone: str | None = None,
    phone_verified: bool = False,
    first_name: str = '',
    last_name: str = '',
) -> tuple[User, SocialIdentity, bool]:
    """
    Linking priority after normalization:

    1. Existing SocialIdentity for provider + id
    2. Verified email match (provider email_verified claim + local is_email_verified)
       — do not treat "email present" as ownership (Facebook)
    3. Verified phone match (is_phone_verified)
    4. Create new password-less customer

    Returns (user, social_identity, created_user).
    """
    provider_user_id = str(provider_user_id).strip()
    if not provider_user_id:
        raise ValidationError({'detail': 'Invalid social provider user id.'})

    existing = (
        SocialIdentity.objects.select_related('user')
        .filter(provider=provider, provider_user_id=provider_user_id)
        .first()
    )
    if existing is not None:
        return existing.user, existing, False

    # Only trust explicit provider-asserted verified email (callers must not pass
    # True merely because an email string was returned).
    normalized_email = normalize_email(email) if email else ''
    canonical_phone = None
    if phone:
        try:
            canonical_phone = normalize_phone_number(phone)
        except PhoneNormalizationError:
            canonical_phone = None

    user = None

    if email_verified and normalized_email:
        profile = (
            CustomerProfile.objects.select_related('user')
            .filter(is_email_verified=True, user__email__iexact=normalized_email)
            .first()
        )
        if profile is not None:
            user = profile.user

    if user is None and phone_verified and canonical_phone:
        profile = (
            CustomerProfile.objects.select_related('user')
            .filter(is_phone_verified=True, phone=canonical_phone)
            .first()
        )
        if profile is not None:
            user = profile.user

    created_user = False
    if user is None:
        user, _profile = create_social_customer(
            email=normalized_email,
            first_name=first_name,
            last_name=last_name,
            phone=canonical_phone,
            email_verified=bool(email_verified and normalized_email),
            phone_verified=bool(phone_verified and canonical_phone),
        )
        created_user = True

    conflict = (
        SocialIdentity.objects.filter(provider=provider, provider_user_id=provider_user_id)
        .exclude(user=user)
        .first()
    )
    if conflict is not None:
        raise SocialLinkConflict()

    identity, _ = SocialIdentity.objects.get_or_create(
        provider=provider,
        provider_user_id=provider_user_id,
        defaults={
            'user': user,
            'email_at_link': normalized_email,
        },
    )
    if identity.user_id != user.id:
        raise SocialLinkConflict()

    return user, identity, created_user
