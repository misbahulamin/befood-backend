"""Validation event recording and share tracking."""

from __future__ import annotations

from django.utils import timezone

from referrals.models import ReferralProfile, ReferralValidationEvent


def record_validation_event(
    *,
    code: str,
    is_valid: bool,
    reason: str = '',
    referrer=None,
    client_ip: str | None = None,
    user_agent: str = '',
) -> ReferralValidationEvent:
    return ReferralValidationEvent.objects.create(
        code=(code or '').strip().upper()[:16],
        is_valid=is_valid,
        reason=(reason or '')[:64],
        referrer=referrer,
        client_ip=client_ip,
        user_agent=(user_agent or '')[:255],
    )


def record_share(profile: ReferralProfile) -> ReferralProfile:
    profile.share_count = (profile.share_count or 0) + 1
    profile.last_shared_at = timezone.now()
    profile.save(update_fields=['share_count', 'last_shared_at', 'updated_at'])
    return profile
