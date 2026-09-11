"""Referral query helpers for customer and admin APIs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from orders.models import CustomerSubscription
from referrals.models import (
    ReferralCommission,
    ReferralRelationship,
    ReferralValidationEvent,
)
from referrals.services.eligibility import is_referrer_eligible
from referrals.services.codes import ensure_referral_profile


def build_referral_link(code: str) -> str:
    from django.conf import settings

    base = getattr(settings, 'REFERRAL_LINK_BASE_URL', 'https://befood.com.bd/invite')
    base = (base or '').rstrip('/')
    return f'{base}?code={code}'


def customer_referral_summary(customer) -> dict:
    profile = ensure_referral_profile(customer)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    earned = ReferralCommission.objects.filter(
        referrer=customer,
        status=ReferralCommission.Status.SUCCESS,
        is_manual=False,
    )
    lifetime = earned.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0.00')
    monthly = earned.filter(created_at__gte=month_start).aggregate(
        total=Sum('commission_amount')
    )['total'] or Decimal('0.00')
    referred_count = ReferralRelationship.objects.filter(referrer=customer).count()
    return {
        'code': profile.code,
        'link': build_referral_link(profile.code),
        'is_usable': is_referrer_eligible(customer),
        'share_count': profile.share_count,
        'last_shared_at': profile.last_shared_at,
        'referred_user_count': referred_count,
        'lifetime_commission': lifetime,
        'month_commission': monthly,
    }


def referrer_relationships_qs(customer):
    return (
        ReferralRelationship.objects.filter(referrer=customer)
        .select_related('referred', 'referred__user')
        .annotate(
            commission_total=Sum(
                'referred__referral_commissions_generated__commission_amount',
                filter=Q(
                    referred__referral_commissions_generated__status=ReferralCommission.Status.SUCCESS,
                    referred__referral_commissions_generated__referrer=customer,
                ),
            )
        )
        .order_by('-attributed_at')
    )


def referrer_commissions_qs(customer):
    return (
        ReferralCommission.objects.filter(referrer=customer)
        .select_related('referred', 'referred__user', 'order_delivery')
        .order_by('-created_at')
    )


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def admin_analytics(*, date_from=None, date_to=None) -> dict:
    from datetime import datetime

    def _coerce(value):
        if value is None or value == '':
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            return None

    date_from = _coerce(date_from)
    date_to = _coerce(date_to)

    rel_qs = ReferralRelationship.objects.all()
    comm_qs = ReferralCommission.objects.filter(status=ReferralCommission.Status.SUCCESS)
    val_qs = ReferralValidationEvent.objects.all()

    if date_from:
        rel_qs = rel_qs.filter(attributed_at__gte=date_from)
        comm_qs = comm_qs.filter(created_at__gte=date_from)
        val_qs = val_qs.filter(created_at__gte=date_from)
    if date_to:
        rel_qs = rel_qs.filter(attributed_at__lte=date_to)
        comm_qs = comm_qs.filter(created_at__lte=date_to)
        val_qs = val_qs.filter(created_at__lte=date_to)

    total_relationships = rel_qs.count()
    active_referrer_ids = set(
        CustomerSubscription.objects.filter(
            status=CustomerSubscription.Status.ACTIVE,
            customer_id__in=rel_qs.values_list('referrer_id', flat=True).distinct(),
        ).values_list('customer_id', flat=True)
    )
    total_commission = comm_qs.aggregate(total=Sum('commission_amount'))['total'] or Decimal(
        '0.00'
    )
    total_validations = val_qs.count()
    successful_validations = val_qs.filter(is_valid=True).count()
    paid_from_referral = (
        CustomerSubscription.objects.filter(
            status=CustomerSubscription.Status.ACTIVE,
            customer_id__in=rel_qs.values_list('referred_id', flat=True),
        )
        .values('customer_id')
        .distinct()
        .count()
    )
    conversion_rate = (
        Decimal(total_relationships) / Decimal(successful_validations)
        if successful_validations
        else Decimal('0.00')
    )
    return {
        'total_relationships': total_relationships,
        'total_active_referrers': len(active_referrer_ids),
        'total_commission_paid': total_commission,
        'total_admin_wallet_deductions': total_commission,
        'total_validations': total_validations,
        'total_successful_validations': successful_validations,
        'total_successful_registrations': total_relationships,
        'total_paid_subscribers_from_referral': paid_from_referral,
        'conversion_rate': conversion_rate.quantize(Decimal('0.0001')),
    }


def admin_relationships_qs(*, filters: dict | None = None):
    qs = ReferralRelationship.objects.select_related(
        'referrer',
        'referrer__user',
        'referred',
        'referred__user',
    ).order_by('-attributed_at')
    filters = filters or {}
    if filters.get('referral_code'):
        qs = qs.filter(referral_code_used__iexact=filters['referral_code'].strip())
    if filters.get('referrer_public_id'):
        qs = qs.filter(referrer__public_id=filters['referrer_public_id'])
    if filters.get('referred_public_id'):
        qs = qs.filter(referred__public_id=filters['referred_public_id'])
    if filters.get('created_from'):
        qs = qs.filter(attributed_at__gte=filters['created_from'])
    if filters.get('created_to'):
        qs = qs.filter(attributed_at__lte=filters['created_to'])
    return qs


def admin_commissions_qs(*, filters: dict | None = None):
    qs = ReferralCommission.objects.select_related(
        'referrer',
        'referrer__user',
        'referred',
        'referred__user',
        'order_delivery',
        'admin_wallet_transaction',
        'customer_wallet_transaction',
    ).order_by('-created_at')
    filters = filters or {}
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])
    if filters.get('referral_code'):
        qs = qs.filter(
            referrer__referral_profile__code__iexact=filters['referral_code'].strip()
        )
    if filters.get('referrer_public_id'):
        qs = qs.filter(referrer__public_id=filters['referrer_public_id'])
    if filters.get('referred_public_id'):
        qs = qs.filter(referred__public_id=filters['referred_public_id'])
    if filters.get('created_from'):
        qs = qs.filter(created_at__gte=filters['created_from'])
    if filters.get('created_to'):
        qs = qs.filter(created_at__lte=filters['created_to'])
    return qs
