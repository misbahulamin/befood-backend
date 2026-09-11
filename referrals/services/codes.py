"""Referral code generation and profile ensure/backfill."""

from __future__ import annotations

import secrets
import string

from django.db import IntegrityError, transaction

from referrals.models import ReferralProfile

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_PREFIX = 'BEF'
CODE_SUFFIX_LEN = 8
MAX_ATTEMPTS = 32


def generate_referral_code() -> str:
    suffix = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_SUFFIX_LEN))
    return f'{CODE_PREFIX}{suffix}'


@transaction.atomic
def ensure_referral_profile(customer) -> ReferralProfile:
    existing = getattr(customer, 'referral_profile', None)
    if existing is not None:
        return existing
    profile = ReferralProfile.objects.filter(customer=customer).first()
    if profile is not None:
        return profile

    for _ in range(MAX_ATTEMPTS):
        code = generate_referral_code()
        try:
            return ReferralProfile.objects.create(customer=customer, code=code)
        except IntegrityError:
            continue
    raise RuntimeError('Unable to allocate a unique referral code.')


def backfill_missing_referral_profiles(*, limit: int | None = None) -> int:
    from user_management.models import CustomerProfile

    qs = CustomerProfile.objects.filter(referral_profile__isnull=True).order_by('id')
    if limit is not None:
        qs = qs[:limit]
    created = 0
    for customer in qs.iterator():
        ensure_referral_profile(customer)
        created += 1
    return created
