"""Factory helpers for phone-only and social-only customer accounts."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from user_management.models import CustomerProfile
from user_management.services.identity_normalization import normalize_email, normalize_phone_number
from user_management.services.profile_completion import update_profile_completion


def _unique_username(prefix: str) -> str:
    base = slugify(prefix)[:20] or 'customer'
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        suffix = uuid.uuid4().hex[:6]
        username = f'{base}-{suffix}'
        counter += 1
        if counter > 20:
            username = f'customer-{uuid.uuid4().hex[:12]}'
            break
    return username


@transaction.atomic
def create_phone_only_customer(phone: str) -> tuple[User, CustomerProfile]:
    """Create a password-less customer with verified phone only."""
    canonical = normalize_phone_number(phone)
    user = User(username=_unique_username(f'phone-{canonical[-4:]}'), email='')
    user.set_unusable_password()
    user.save()

    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)

    now = timezone.now()
    profile = CustomerProfile.objects.create(
        user=user,
        phone=canonical,
        is_phone_verified=True,
        phone_verified_at=now,
        profile_completed=False,
        profile_completion_percentage=0,
    )
    update_profile_completion(profile)
    return user, profile


@transaction.atomic
def create_social_customer(
    *,
    email: str = '',
    first_name: str = '',
    last_name: str = '',
    phone: str | None = None,
    email_verified: bool = False,
    phone_verified: bool = False,
) -> tuple[User, CustomerProfile]:
    """Create a password-less customer from a social provider profile."""
    normalized_email = normalize_email(email) if email else ''
    prefix = normalized_email.split('@')[0] if normalized_email else 'social'
    user = User(
        username=_unique_username(prefix),
        email=normalized_email,
        first_name=(first_name or '')[:150],
        last_name=(last_name or '')[:150],
    )
    user.set_unusable_password()
    user.save()

    group, _ = Group.objects.get_or_create(name='CUSTOMER')
    user.groups.add(group)

    now = timezone.now()
    canonical_phone = None
    if phone:
        canonical_phone = normalize_phone_number(phone)

    profile = CustomerProfile.objects.create(
        user=user,
        phone=canonical_phone,
        is_email_verified=bool(email_verified and normalized_email),
        email_verified_at=now if (email_verified and normalized_email) else None,
        is_phone_verified=bool(phone_verified and canonical_phone),
        phone_verified_at=now if (phone_verified and canonical_phone) else None,
        profile_completed=False,
        profile_completion_percentage=0,
    )
    update_profile_completion(profile)
    return user, profile
