from django.db.models import Count, Q, Sum

from onahar.models import (
    OnaharContribution,
    OnaharDistribution,
    OnaharFundLedgerEntry,
    OnaharMonthlyProgress,
    OnaharPointEvent,
    OnaharPrivacyPreference,
)
from onahar.services.fund import fund_summary, get_or_create_settings
from onahar.services.privacy import current_year_month, customer_display_name, get_or_create_privacy


def build_public_stats() -> dict:
    summary = fund_summary()
    settings_obj = get_or_create_settings()
    year_month = current_year_month()
    current_month_contributions = (
        OnaharContribution.objects.filter(year_month=year_month).aggregate(total=Sum('meals'))[
            'total'
        ]
        or 0
    )
    total_contributors = (
        OnaharContribution.objects.values('customer_id')
        .annotate(net=Sum('meals'))
        .filter(net__gt=0)
        .count()
    )
    total_campaigns = OnaharDistribution.objects.filter(
        status=OnaharDistribution.Status.PUBLISHED
    ).count()
    return {
        'total_meals_contributed': summary['total_contributed_meals'],
        'total_meals_distributed': summary['total_distributed_meals'],
        'available_meals': summary['available_meals'],
        'total_contributors': total_contributors,
        'total_distribution_campaigns': total_campaigns,
        'current_month_contributions': max(0, current_month_contributions),
        'current_contribution_target': settings_obj.contribution_target,
    }


def leaderboard_queryset():
    return (
        OnaharContribution.objects.values('customer_id')
        .annotate(total_meals=Sum('meals'))
        .filter(total_meals__gt=0)
        .order_by('-total_meals', 'customer_id')
    )


def customer_lifetime_stats(customer) -> dict:
    eligible = OnaharPointEvent.objects.filter(
        customer=customer,
        event_type=OnaharPointEvent.EventType.CREDIT,
    ).count()
    reversed_count = OnaharPointEvent.objects.filter(
        customer=customer,
        event_type=OnaharPointEvent.EventType.REVERSE,
    ).count()
    contributed = (
        OnaharContribution.objects.filter(customer=customer).aggregate(total=Sum('meals'))['total']
        or 0
    )
    return {
        'total_eligible_meals': max(0, eligible - reversed_count),
        'total_onahar_meals_contributed': max(0, contributed),
    }


def customer_ranking(customer) -> int | None:
    rows = list(leaderboard_queryset())
    for idx, row in enumerate(rows, start=1):
        if row['customer_id'] == customer.pk:
            return idx
    return None


def get_or_open_current_progress(customer) -> OnaharMonthlyProgress:
    from onahar.services.contribution import _open_or_get_progress
    from django.db import transaction

    year_month = current_year_month()
    with transaction.atomic():
        return _open_or_get_progress(customer, year_month)


def privacy_display_for_customer_id(customer_id: int) -> str:
    from user_management.models import CustomerProfile

    customer = CustomerProfile.objects.select_related('user').get(pk=customer_id)
    return customer_display_name(customer)
