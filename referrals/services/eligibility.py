"""Referral eligibility helpers."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q

from orders.services.subscription_service import get_active_subscription
from referrals.models import ReferralProfile

INACTIVE_REFERRER_MESSAGE = (
    'Your referrer does not have an active meal subscription.'
)

REASON_REFERRER_INACTIVE = 'REFERRER_INACTIVE'
REASON_REFERRED_INACTIVE = 'REFERRED_INACTIVE'
REASON_REFERRER_MEAL_NOT_CONSUMED = 'REFERRER_MEAL_NOT_CONSUMED'
RETRYABLE_SKIP_REASONS = frozenset({REASON_REFERRER_MEAL_NOT_CONSUMED})


class ReferralError(Exception):
    def __init__(self, message: str, *, code: str = 'REFERRAL_ERROR'):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AccrualEligibility:
    """Result of co-consumption + dual-subscription checks for accrual."""

    ok: bool
    reason: str = ''
    detail: str = ''


def is_referrer_eligible(customer) -> bool:
    return get_active_subscription(customer) is not None


def get_profile_by_code(code: str) -> ReferralProfile | None:
    normalized = (code or '').strip().upper()
    if not normalized:
        return None
    return (
        ReferralProfile.objects.select_related('customer', 'customer__user')
        .filter(code=normalized)
        .first()
    )


def validate_code_for_signup(code: str) -> ReferralProfile:
    profile = get_profile_by_code(code)
    if profile is None:
        raise ReferralError('Invalid referral code.', code='REFERRAL_CODE_INVALID')
    if not is_referrer_eligible(profile.customer):
        raise ReferralError(INACTIVE_REFERRER_MESSAGE, code='REFERRER_INACTIVE')
    return profile


def referrer_has_matching_delivered_meal(
    referrer,
    *,
    service_date,
    meal_period: str,
) -> bool:
    """
    Referrer consumption = OrderDelivery.status delivered for same date/period.

    Does NOT require payment_status=charged (complimentary / special cases count).
    Preferred path uses subscription__customer (+ optional historical order parent).
    Unique (subscription, service_date, meal_period) covers the hot lookup.
    """
    from orders.models import OrderDelivery

    period = (meal_period or '').strip()
    if service_date is None or not period:
        return False

    return OrderDelivery.objects.filter(
        Q(subscription__customer=referrer) | Q(order__customer=referrer),
        service_date=service_date,
        meal_period=period,
        status=OrderDelivery.DeliveryStatus.DELIVERED,
    ).exists()


def evaluate_accrual_party_eligibility(
    *,
    referrer,
    referred,
    service_date,
    meal_period: str,
) -> AccrualEligibility:
    """
    Dual active subscription + referrer same-day same-meal delivered.

    Referred delivery charged check belongs in the commission accrual entrypoint
    (money basis); this helper focuses on party/co-consumption gates.
    """
    if get_active_subscription(referrer) is None:
        return AccrualEligibility(
            ok=False,
            reason=REASON_REFERRER_INACTIVE,
            detail='Referrer has no active meal subscription.',
        )
    if get_active_subscription(referred) is None:
        return AccrualEligibility(
            ok=False,
            reason=REASON_REFERRED_INACTIVE,
            detail='Referred customer has no active meal subscription.',
        )
    if not referrer_has_matching_delivered_meal(
        referrer,
        service_date=service_date,
        meal_period=meal_period,
    ):
        return AccrualEligibility(
            ok=False,
            reason=REASON_REFERRER_MEAL_NOT_CONSUMED,
            detail=(
                'Referrer has no matching delivered meal for the same '
                'service_date and meal_period.'
            ),
        )
    return AccrualEligibility(ok=True)


def is_retryable_skip(commission) -> bool:
    from referrals.models import ReferralCommission

    return (
        commission is not None
        and commission.status == ReferralCommission.Status.SKIPPED
        and (commission.status_reason or '') in RETRYABLE_SKIP_REASONS
        and not commission.is_manual
    )
