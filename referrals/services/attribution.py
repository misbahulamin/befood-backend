"""Signup attribution — mobile only, immutable one-referrer."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from referrals.models import ReferralRelationship
from referrals.services.eligibility import (
    ReferralError,
    is_referrer_eligible,
    validate_code_for_signup,
    INACTIVE_REFERRER_MESSAGE,
)


def _normalize_client(client_type: str | None) -> str:
    return (client_type or '').strip().lower() or 'web'


@transaction.atomic
def attribute_on_signup(
    *,
    referred_customer,
    referral_code: str | None,
    client_type: str | None,
    allow_without_code: bool = True,
) -> ReferralRelationship | None:
    """
    Create an immutable referral relationship for a newly created customer.

    Web clients that supply a referral_code are rejected with 422-equivalent error.
    """
    code = (referral_code or '').strip()
    client = _normalize_client(client_type)

    if not code:
        if allow_without_code:
            return None
        raise ReferralError('referral_code is required.', code='REFERRAL_CODE_REQUIRED')

    if client != 'mobile':
        raise ReferralError(
            'Referral registration is only allowed from the mobile app.',
            code='REFERRAL_MOBILE_ONLY',
        )

    if ReferralRelationship.objects.filter(referred=referred_customer).exists():
        raise ReferralError(
            'Referral relationship already exists and cannot be changed.',
            code='REFERRAL_ALREADY_ATTRIBUTED',
        )

    profile = validate_code_for_signup(code)
    if profile.customer_id == referred_customer.pk:
        raise ReferralError(
            'You cannot use your own referral code.',
            code='REFERRAL_SELF_NOT_ALLOWED',
        )

    # Re-check under race (subscription cancelled between validate and write).
    if not is_referrer_eligible(profile.customer):
        raise ReferralError(INACTIVE_REFERRER_MESSAGE, code='REFERRER_INACTIVE')

    try:
        return ReferralRelationship.objects.create(
            referrer=profile.customer,
            referred=referred_customer,
            referral_code_used=profile.code,
            source_client=ReferralRelationship.SourceClient.MOBILE,
            attributed_at=timezone.now(),
        )
    except IntegrityError as exc:
        existing = ReferralRelationship.objects.filter(referred=referred_customer).first()
        if existing is not None:
            raise ReferralError(
                'Referral relationship already exists and cannot be changed.',
                code='REFERRAL_ALREADY_ATTRIBUTED',
            ) from exc
        raise
