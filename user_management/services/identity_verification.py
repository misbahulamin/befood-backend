"""Unified customer identity verification for multi-provider auth."""

from __future__ import annotations

from user_management.models import SocialIdentity

IDENTITY_VERIFICATION_REQUIRED_MESSAGE = (
    'Identity verification is required before placing an order.'
)
IDENTITY_VERIFICATION_REQUIRED_SUBSCRIBE_MESSAGE = (
    'Identity verification is required before subscribing.'
)


def _customer_profile(user):
    return getattr(user, 'customer_profile', None)


def has_google_identity(user) -> bool:
    return SocialIdentity.objects.filter(
        user_id=user.pk,
        provider=SocialIdentity.Provider.GOOGLE,
    ).exists()


def has_facebook_identity(user) -> bool:
    return SocialIdentity.objects.filter(
        user_id=user.pk,
        provider=SocialIdentity.Provider.FACEBOOK,
    ).exists()


def is_customer_identity_verified(user) -> bool:
    """
    True when the customer has any trusted provider identity.

    Extend this helper when adding providers (Apple, WhatsApp, etc.).
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        # Guests / anonymous principals are never identity-verified here.
        return False

    profile = _customer_profile(user)
    if profile is None:
        return False

    if profile.is_email_verified:
        return True
    if profile.is_phone_verified:
        return True
    if has_google_identity(user):
        return True
    if has_facebook_identity(user):
        return True
    return False


def build_verification_status(user) -> dict[str, bool]:
    """Per-provider flags plus aggregate identity_verified for auth responses."""
    profile = _customer_profile(user)
    email_verified = bool(profile and profile.is_email_verified)
    phone_verified = bool(profile and profile.is_phone_verified)
    google_verified = bool(user and user.pk and has_google_identity(user))
    facebook_verified = bool(user and user.pk and has_facebook_identity(user))
    identity_verified = any(
        [email_verified, phone_verified, google_verified, facebook_verified]
    )
    return {
        'email_verified': email_verified,
        'phone_verified': phone_verified,
        'google_verified': google_verified,
        'facebook_verified': facebook_verified,
        'identity_verified': identity_verified,
    }


def safe_user_email(user) -> str:
    """Return user email as string; never crash on null/empty phone-only accounts."""
    return (getattr(user, 'email', None) or '') if user is not None else ''
