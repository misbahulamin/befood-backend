"""Validation / attribution event recording and share tracking."""

from __future__ import annotations

import logging

from django.utils import timezone

from referrals.models import ReferralAttributionEvent, ReferralProfile, ReferralValidationEvent

logger = logging.getLogger(__name__)


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


def record_attribution_event(
    *,
    customer=None,
    referral_code: str,
    client_type: str = '',
    stage: str,
    outcome: str,
    error_code: str = '',
) -> ReferralAttributionEvent:
    """Persist a structured attribution outcome (skips must include error_code)."""
    event = ReferralAttributionEvent.objects.create(
        customer=customer,
        referral_code=(referral_code or '').strip().upper()[:16],
        client_type=(client_type or '').strip().lower()[:16],
        stage=stage,
        outcome=outcome,
        error_code=(error_code or '')[:64],
    )
    logger.info(
        'Referral attribution outcome customer_id=%s code=%s client_type=%s '
        'stage=%s outcome=%s error_code=%s',
        getattr(customer, 'pk', None),
        event.referral_code,
        event.client_type,
        event.stage,
        event.outcome,
        event.error_code or '-',
    )
    return event


def record_share(profile: ReferralProfile) -> ReferralProfile:
    profile.share_count = (profile.share_count or 0) + 1
    profile.last_shared_at = timezone.now()
    profile.save(update_fields=['share_count', 'last_shared_at', 'updated_at'])
    return profile
