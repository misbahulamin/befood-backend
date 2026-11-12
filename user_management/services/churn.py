"""Admin churn list, analytics, CSV, and follow-up helpers (no Request objects)."""

from __future__ import annotations

import csv
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import (
    Count,
    DateField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from orders.models import (
    ChurnFollowUp,
    CustomerSubscription,
    OrderDelivery,
    SubscriptionCancellation,
)
from orders.services.customer_lifecycle import (
    LIFECYCLE_AT_RISK,
    LIFECYCLE_NEVER_SUBSCRIBED,
    LIFECYCLE_UNSUBSCRIBED,
    LIFECYCLE_VALUES,
    LEADING_SIGNAL_LOOKBACK_DAYS,
    annotate_lifecycle,
    business_calendar_today,
    churn_date_annotation_subquery,
    count_low_balance_blocked_days,
    count_meal_off_days,
    filter_by_lifecycle,
    month_bounds_dhaka,
    tenure_days_for_subscription,
    to_business_date,
)
from orders.services.meal_off import CUTOFF_PASSED_NOTE
from user_management.models import CustomerProfile
from user_management.services.admin_customer import (
    LIST_QUERY_ALLOWLIST as CUSTOMER_LIST_ALLOWLIST,
    SORT_ALLOWLIST as CUSTOMER_SORT_ALLOWLIST,
    customer_base_queryset,
    reject_unknown_query_params,
)
from user_management.services.profile_picture import get_profile_picture_url
from user_management.validators import format_bd_phone_e164

BUSINESS_TZ = ZoneInfo('Asia/Dhaka')

CHURN_LIST_ALLOWLIST = CUSTOMER_LIST_ALLOWLIST | frozenset(
    {
        'lifecycle',
        'churned_from',
        'churned_to',
        'cancel_reason',
        'package',
        'format',
    }
)

CHURN_SORT_ALLOWLIST = {
    **CUSTOMER_SORT_ALLOWLIST,
    'churn_date': ('churn_date', 'public_id'),
    '-churn_date': ('-churn_date', 'public_id'),
    'tenure_days': ('tenure_days', 'public_id'),
    '-tenure_days': ('-tenure_days', 'public_id'),
}

ANALYTICS_QUERY_ALLOWLIST = frozenset({'from', 'to'})

FOLLOW_UP_LIST_ALLOWLIST = frozenset(
    {
        'customer_public_id',
        'status',
        'page',
        'page_size',
    }
)

TENURE_BUCKETS = (
    ('0-7', 0, 7),
    ('8-14', 8, 14),
    ('15-30', 15, 30),
    ('31-60', 31, 60),
    ('60+', 61, None),
)


def _parse_date(raw: str | None, field: str) -> date | None:
    if raw is None or raw == '':
        return None
    parsed = parse_date(str(raw).strip())
    if parsed is None:
        raise ValidationError({field: ['Invalid date. Use YYYY-MM-DD.']})
    return parsed


def enrich_customer_churn_annotations(
    queryset: QuerySet[CustomerProfile],
    *,
    today: date | None = None,
) -> QuerySet[CustomerProfile]:
    """Annotate lifecycle + churn list enrichment fields (set-based)."""
    today = business_calendar_today(today=today)
    qs = annotate_lifecycle(queryset, today=today)

    latest_cancelled = CustomerSubscription.objects.filter(
        customer_id=OuterRef('pk'),
        status=CustomerSubscription.Status.CANCELLED,
    ).order_by('-cancel_effective_on', '-cancelled_at', '-pk')

    latest_any_sub = CustomerSubscription.objects.filter(
        customer_id=OuterRef('pk'),
    ).order_by('-created_at', '-pk')

    latest_reason = SubscriptionCancellation.objects.filter(
        customer_id=OuterRef('pk'),
    ).order_by('-created_at', '-pk')

    latest_follow_up = ChurnFollowUp.objects.filter(
        customer_id=OuterRef('pk'),
    ).order_by('-updated_at', '-pk')

    delivered = OrderDelivery.DeliveryStatus.DELIVERED

    return qs.annotate(
        churn_date=churn_date_annotation_subquery(),
        last_cancel_reason=Subquery(latest_reason.values('reason_code')[:1]),
        last_subscription_package=Coalesce(
            Subquery(
                CustomerSubscription.objects.filter(
                    customer_id=OuterRef('pk'),
                    status=CustomerSubscription.Status.ACTIVE,
                )
                .order_by('-created_at', '-pk')
                .values('meal_name_snapshot')[:1]
            ),
            Subquery(latest_cancelled.values('meal_name_snapshot')[:1]),
            Subquery(latest_any_sub.values('meal_name_snapshot')[:1]),
        ),
        last_subscription_started_on=Coalesce(
            Subquery(
                CustomerSubscription.objects.filter(
                    customer_id=OuterRef('pk'),
                    status=CustomerSubscription.Status.ACTIVE,
                )
                .order_by('-created_at', '-pk')
                .values('started_on')[:1]
            ),
            Subquery(latest_cancelled.values('started_on')[:1]),
        ),
        total_meals_delivered=Count(
            'meal_subscriptions__deliveries',
            filter=Q(meal_subscriptions__deliveries__status=delivered),
            distinct=True,
        ),
        follow_up_status=Subquery(latest_follow_up.values('status')[:1]),
        follow_up_public_id=Subquery(latest_follow_up.values('public_id')[:1]),
    )


def apply_lifecycle_churn_filters(
    queryset: QuerySet[CustomerProfile],
    params,
    *,
    today: date | None = None,
    default_lifecycle: str | None = None,
) -> QuerySet[CustomerProfile]:
    """Apply lifecycle / churn date / reason / package filters + tenure annotation."""
    from django.db.models.functions import ExtractDay

    today = business_calendar_today(today=today)
    if 'lifecycle' not in queryset.query.annotations:
        queryset = enrich_customer_churn_annotations(queryset, today=today)

    lifecycle = (params.get('lifecycle') or '').strip() or default_lifecycle
    if lifecycle:
        if lifecycle not in LIFECYCLE_VALUES:
            raise ValidationError(
                {
                    'lifecycle': [
                        f'Unsupported lifecycle. Allowed: {", ".join(sorted(LIFECYCLE_VALUES))}.'
                    ]
                }
            )
        queryset = queryset.filter(lifecycle=lifecycle)

    churned_from = _parse_date(params.get('churned_from'), 'churned_from')
    churned_to = _parse_date(params.get('churned_to'), 'churned_to')
    if churned_from is not None:
        queryset = queryset.filter(churn_date__gte=churned_from)
    if churned_to is not None:
        queryset = queryset.filter(churn_date__lte=churned_to)

    cancel_reason = (params.get('cancel_reason') or '').strip()
    if cancel_reason:
        valid = {c.value for c in SubscriptionCancellation.ReasonCode}
        if cancel_reason not in valid:
            raise ValidationError({'cancel_reason': ['Unsupported cancel_reason.']})
        queryset = queryset.filter(last_cancel_reason=cancel_reason)

    package = (params.get('package') or '').strip()
    if package:
        queryset = queryset.filter(
            meal_subscriptions__meal__public_id=package,
        ).distinct()

    return queryset


def apply_churn_filters(
    queryset: QuerySet[CustomerProfile],
    params,
    *,
    today: date | None = None,
    default_lifecycle: str | None = None,
    allowlist: frozenset[str] | None = None,
) -> QuerySet[CustomerProfile]:
    """Filters for GET /api/v1/web/churn/customers/ (default unsubscribed)."""
    today = business_calendar_today(today=today)
    allow = allowlist or CHURN_LIST_ALLOWLIST
    reject_unknown_query_params(params, allow)

    from django.http import QueryDict

    qd = QueryDict(mutable=True)
    for key in params.keys():
        if key in {
            'lifecycle',
            'churned_from',
            'churned_to',
            'cancel_reason',
            'package',
            'format',
        }:
            continue
        if key == 'sort':
            continue
        values = params.getlist(key) if hasattr(params, 'getlist') else [params.get(key)]
        for v in values:
            if v is not None:
                qd.appendlist(key, v)
    qd['sort'] = '-date_joined'

    # Import locally to avoid circular apply during module import.
    from user_management.services.admin_customer import (
        apply_customer_list_filters as _apply_base,
    )

    # Temporarily skip lifecycle enrichment inside base apply by using a thin path:
    # call reject + filters without the churn enrichment block via duplicated base filters.
    # Simpler: annotate after a minimal filter set.
    q = (params.get('q') or '').strip()
    if q:
        from user_management.services.admin_people_search import build_customer_people_q

        queryset = queryset.filter(build_customer_people_q(q))

    queryset = enrich_customer_churn_annotations(queryset, today=today)
    queryset = apply_lifecycle_churn_filters(
        queryset,
        params,
        today=today,
        default_lifecycle=default_lifecycle,
    )

    sort_key = (params.get('sort') or '-churn_date').strip()
    # Tenure sort falls back to churn_date (tenure is derived in serializers).
    if sort_key in ('tenure_days', '-tenure_days'):
        sort_key = '-churn_date' if sort_key.startswith('-') else 'churn_date'
    order_by = CHURN_SORT_ALLOWLIST.get(sort_key)
    if order_by is None:
        raise ValidationError(
            {
                'sort': [
                    f'Unsupported sort. Allowed: {", ".join(sorted(CHURN_SORT_ALLOWLIST))}.'
                ]
            }
        )
    return queryset.order_by(*order_by)


def serialize_churn_customer_row(customer: CustomerProfile, *, request=None) -> dict[str, Any]:
    user = customer.user
    name = f'{user.first_name} {user.last_name}'.strip() or user.email
    wallet_balance = None
    try:
        wallet_balance = f'{customer.wallet.balance:.2f}'
    except Exception:
        pass

    churn_date = getattr(customer, 'churn_date', None)
    started = getattr(customer, 'last_subscription_started_on', None)
    tenure = getattr(customer, 'tenure_days', None)
    if tenure is None and churn_date is not None and started is not None:
        tenure = max((churn_date - started).days, 0)
    elif tenure is not None and hasattr(tenure, 'days'):
        tenure = tenure.days

    return {
        'public_id': str(customer.public_id),
        'user_id': user.pk,
        'name': name,
        'email': user.email,
        'phone': format_bd_phone_e164(customer.phone),
        'profile_picture_url': get_profile_picture_url(customer, request=request),
        'is_active': user.is_active,
        'lifecycle': getattr(customer, 'lifecycle', None),
        'last_subscription_package': getattr(customer, 'last_subscription_package', None),
        'churn_date': churn_date.isoformat() if churn_date else None,
        'tenure_days': tenure,
        'total_meals_delivered': getattr(customer, 'total_meals_delivered', 0) or 0,
        'last_cancel_reason': getattr(customer, 'last_cancel_reason', None),
        'wallet_balance': wallet_balance,
        'follow_up_status': getattr(customer, 'follow_up_status', None),
        'follow_up_public_id': (
            str(getattr(customer, 'follow_up_public_id'))
            if getattr(customer, 'follow_up_public_id', None)
            else None
        ),
        'meal_service_blocked_low_balance': customer.meal_service_blocked_low_balance,
        'registered_at': user.date_joined.isoformat().replace('+00:00', 'Z'),
    }


def build_churn_customers_queryset(params, *, today: date | None = None) -> QuerySet:
    qs = customer_base_queryset()
    return apply_churn_filters(
        qs,
        params,
        today=today,
        default_lifecycle=LIFECYCLE_UNSUBSCRIBED,
        allowlist=CHURN_LIST_ALLOWLIST,
    )


def churn_customers_csv_response(queryset: QuerySet, *, request=None) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            'public_id',
            'name',
            'email',
            'phone',
            'lifecycle',
            'churn_date',
            'tenure_days',
            'last_subscription_package',
            'last_cancel_reason',
            'total_meals_delivered',
            'wallet_balance',
            'follow_up_status',
        ]
    )
    for customer in queryset.iterator(chunk_size=200):
        row = serialize_churn_customer_row(customer, request=request)
        writer.writerow(
            [
                row['public_id'],
                row['name'],
                row['email'],
                row['phone'] or '',
                row['lifecycle'] or '',
                row['churn_date'] or '',
                row['tenure_days'] if row['tenure_days'] is not None else '',
                row['last_subscription_package'] or '',
                row['last_cancel_reason'] or '',
                row['total_meals_delivered'],
                row['wallet_balance'] or '',
                row['follow_up_status'] or '',
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="churn-customers.csv"'
    return response


def _period_bounds(params) -> tuple[date, date]:
    start = _parse_date(params.get('from'), 'from')
    end = _parse_date(params.get('to'), 'to')
    if start is None or end is None:
        raise ValidationError({'from': ['Both from and to (YYYY-MM-DD) are required.']})
    if end < start:
        raise ValidationError({'to': ['to must be on or after from.']})
    if (end - start).days > 366:
        raise ValidationError({'to': ['Date range cannot exceed 366 days.']})
    return start, end


def _churned_subscriptions_in_period(start: date, end: date) -> QuerySet:
    return (
        CustomerSubscription.objects.filter(status=CustomerSubscription.Status.CANCELLED)
        .annotate(
            churn_d=Coalesce(
                'cancel_effective_on',
                TruncDate('cancelled_at', tzinfo=BUSINESS_TZ),
                output_field=DateField(),
            )
        )
        .filter(churn_d__gte=start, churn_d__lte=end)
        .select_related('meal', 'customer', 'cancellation')
    )


def build_churn_analytics(params) -> dict[str, Any]:
    reject_unknown_query_params(params, ANALYTICS_QUERY_ALLOWLIST)
    start, end = _period_bounds(params)
    today = business_calendar_today()

    churned_subs = list(_churned_subscriptions_in_period(start, end))
    churned_customer_ids = {s.customer_id for s in churned_subs}
    churned_count = len(churned_customer_ids)

    # Active at period start: had active sub overlapping start (started_on <= start
    # and (still active OR cancelled with churn_date >= start)).
    active_at_start = (
        CustomerSubscription.objects.filter(
            started_on__lte=start,
        )
        .filter(
            Q(status=CustomerSubscription.Status.ACTIVE)
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__gte=start,
            )
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__isnull=True,
                cancelled_at__date__gte=start,
            )
        )
        .values('customer_id')
        .distinct()
        .count()
    )
    churn_rate = (
        round((churned_count / active_at_start) * 100, 2) if active_at_start else 0.0
    )

    new_subs = CustomerSubscription.objects.filter(
        started_on__gte=start,
        started_on__lte=end,
    ).count()
    net_growth = new_subs - len(churned_subs)

    # Win-backs in period: active subs started in period with prior cancel before start
    win_back_qs = CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE,
        started_on__gte=start,
        started_on__lte=end,
    ).filter(
        Exists(
            CustomerSubscription.objects.filter(
                customer_id=OuterRef('customer_id'),
                status=CustomerSubscription.Status.CANCELLED,
                started_on__lt=OuterRef('started_on'),
            )
        )
    )
    win_back_count = win_back_qs.count()
    win_back_rate = (
        round((win_back_count / new_subs) * 100, 2) if new_subs else 0.0
    )

    at_risk_count = filter_by_lifecycle(
        CustomerProfile.objects.all(),
        LIFECYCLE_AT_RISK,
        today=today,
    ).count()
    never_subscribed_count = filter_by_lifecycle(
        CustomerProfile.objects.all(),
        LIFECYCLE_NEVER_SUBSCRIBED,
        today=today,
    ).count()

    tenures = []
    for sub in churned_subs:
        t = tenure_days_for_subscription(sub)
        if t is not None:
            tenures.append(t)
    avg_tenure = round(sum(tenures) / len(tenures), 2) if tenures else 0.0
    med_tenure = float(median(tenures)) if tenures else 0.0

    revenue_lost = Decimal('0.00')
    for sub in churned_subs:
        if sub.meal_id and sub.meal.total_price is not None:
            revenue_lost += Decimal(sub.meal.total_price)
    revenue_lost = revenue_lost.quantize(Decimal('0.01'))

    # Breakdowns
    by_reason: dict[str, int] = {}
    by_package: dict[str, int] = {}
    by_period: dict[str, int] = {}
    by_cancelled_by: dict[str, int] = {}
    by_tenure: dict[str, int] = {label: 0 for label, _, _ in TENURE_BUCKETS}

    for sub in churned_subs:
        reason = 'unknown'
        cancelled_by = sub.cancel_source or 'system'
        if hasattr(sub, 'cancellation') and sub.cancellation is not None:
            reason = sub.cancellation.reason_code
            cancelled_by = sub.cancellation.cancelled_by
        by_reason[reason] = by_reason.get(reason, 0) + 1
        pkg = sub.meal_name_snapshot or 'unknown'
        by_package[pkg] = by_package.get(pkg, 0) + 1
        period = sub.meal_period_snapshot or 'unknown'
        by_period[period] = by_period.get(period, 0) + 1
        by_cancelled_by[cancelled_by] = by_cancelled_by.get(cancelled_by, 0) + 1
        t = tenure_days_for_subscription(sub)
        if t is not None:
            for label, lo, hi in TENURE_BUCKETS:
                if hi is None and t >= lo:
                    by_tenure[label] += 1
                    break
                if hi is not None and lo <= t <= hi:
                    by_tenure[label] += 1
                    break

    # Time series daily
    days = (end - start).days + 1
    series = []
    for i in range(days):
        day = start + timedelta(days=i)
        series.append(
            {
                'date': day.isoformat(),
                'new_subscriptions': CustomerSubscription.objects.filter(
                    started_on=day
                ).count(),
                'cancels': sum(
                    1
                    for s in churned_subs
                    if (
                        s.cancel_effective_on == day
                        or (
                            s.cancel_effective_on is None
                            and to_business_date(s.cancelled_at) == day
                        )
                    )
                ),
            }
        )

    # Cohort retention by start month
    cohorts = []
    # Collect distinct start months in range ± lookback for cohorts that can mature
    month_cursor = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    while month_cursor <= end_month:
        m_start = month_cursor
        last_day = monthrange(m_start.year, m_start.month)[1]
        m_end = m_start.replace(day=last_day)
        starters = list(
            CustomerSubscription.objects.filter(
                started_on__gte=m_start,
                started_on__lte=m_end,
            ).only('pk', 'customer_id', 'started_on', 'status', 'cancel_effective_on', 'cancelled_at')
        )
        total = len(starters)
        if total:
            def retained(days_n: int) -> float:
                alive = 0
                for s in starters:
                    checkpoint = s.started_on + timedelta(days=days_n)
                    churn_d = None
                    if s.status == CustomerSubscription.Status.CANCELLED:
                        churn_d = s.cancel_effective_on or to_business_date(s.cancelled_at)
                    if churn_d is None or churn_d > checkpoint:
                        alive += 1
                return round((alive / total) * 100, 2)

            cohorts.append(
                {
                    'start_month': m_start.isoformat()[:7],
                    'cohort_size': total,
                    'retention_7': retained(7),
                    'retention_14': retained(14),
                    'retention_30': retained(30),
                    'retention_60': retained(60),
                }
            )
        # next month
        if m_start.month == 12:
            month_cursor = date(m_start.year + 1, 1, 1)
        else:
            month_cursor = date(m_start.year, m_start.month + 1, 1)

    # Leading signals
    lookback = LEADING_SIGNAL_LOOKBACK_DAYS
    churned_meal_offs = []
    churned_blocks = []
    for sub in churned_subs:
        churn_d = sub.cancel_effective_on or to_business_date(sub.cancelled_at)
        if churn_d is None:
            continue
        window_end = churn_d
        window_start = churn_d - timedelta(days=lookback - 1)
        offs = (
            OrderDelivery.objects.filter(
                subscription_id=sub.pk,
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source__in=(
                    OrderDelivery.SkipSource.CUSTOMER,
                    OrderDelivery.SkipSource.ADMIN,
                ),
                service_date__gte=window_start,
                service_date__lte=window_end,
            )
            .values('service_date')
            .distinct()
            .count()
        )
        blocks = (
            OrderDelivery.objects.filter(
                subscription_id=sub.pk,
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source=OrderDelivery.SkipSource.SYSTEM,
                note=CUTOFF_PASSED_NOTE,
                service_date__gte=window_start,
                service_date__lte=window_end,
            )
            .values('service_date')
            .distinct()
            .count()
        )
        churned_meal_offs.append(offs)
        churned_blocks.append(blocks)

    active_customers = list(
        CustomerProfile.objects.filter(
            meal_subscriptions__status=CustomerSubscription.Status.ACTIVE,
        ).distinct()[:200]
    )
    active_meal_offs = []
    active_blocks = []
    for c in active_customers:
        active_meal_offs.append(count_meal_off_days(c, today=today))
        active_blocks.append(count_low_balance_blocked_days(c, today=today))

    def _avg(vals: list[int]) -> float:
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    return {
        'from': start.isoformat(),
        'to': end.isoformat(),
        'kpis': {
            'churned_count': churned_count,
            'churn_rate_percent': churn_rate,
            'active_at_period_start': active_at_start,
            'net_growth': net_growth,
            'win_back_count': win_back_count,
            'win_back_rate_percent': win_back_rate,
            'at_risk_count': at_risk_count,
            'never_subscribed_count': never_subscribed_count,
            'avg_tenure_days': avg_tenure,
            'median_tenure_days': med_tenure,
            'revenue_lost': f'{revenue_lost:.2f}',
            'currency': 'BDT',
        },
        'breakdowns': {
            'by_reason': [
                {'key': k, 'count': v} for k, v in sorted(by_reason.items())
            ],
            'by_package': [
                {'key': k, 'count': v} for k, v in sorted(by_package.items())
            ],
            'by_meal_period': [
                {'key': k, 'count': v} for k, v in sorted(by_period.items())
            ],
            'by_cancelled_by': [
                {'key': k, 'count': v} for k, v in sorted(by_cancelled_by.items())
            ],
            'by_tenure': [
                {'key': label, 'count': by_tenure[label]} for label, _, _ in TENURE_BUCKETS
            ],
        },
        'time_series': series,
        'cohorts': cohorts,
        'leading_signals': {
            'window_days': lookback,
            'churned_avg_meal_offs': _avg(churned_meal_offs),
            'churned_avg_low_balance_blocks': _avg(churned_blocks),
            'active_avg_meal_offs': _avg(active_meal_offs),
            'active_avg_low_balance_blocks': _avg(active_blocks),
        },
    }


def dashboard_churn_kpis(*, today: date | None = None) -> dict[str, Any]:
    today = business_calendar_today(today=today)
    month_start, month_end = month_bounds_dhaka(reference=today)

    unsubscribed_this_month = (
        enrich_customer_churn_annotations(CustomerProfile.objects.all(), today=today)
        .filter(
            lifecycle=LIFECYCLE_UNSUBSCRIBED,
            churn_date__gte=month_start,
            churn_date__lte=min(month_end, today),
        )
        .count()
    )

    active_at_month_start = (
        CustomerSubscription.objects.filter(started_on__lte=month_start)
        .filter(
            Q(status=CustomerSubscription.Status.ACTIVE)
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__gte=month_start,
            )
            | Q(
                status=CustomerSubscription.Status.CANCELLED,
                cancel_effective_on__isnull=True,
                cancelled_at__date__gte=month_start,
            )
        )
        .values('customer_id')
        .distinct()
        .count()
    )
    churn_rate_this_month = (
        round((unsubscribed_this_month / active_at_month_start) * 100, 2)
        if active_at_month_start
        else 0.0
    )

    at_risk_count = filter_by_lifecycle(
        CustomerProfile.objects.all(),
        LIFECYCLE_AT_RISK,
        today=today,
    ).count()

    won_back_this_month = CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE,
        started_on__gte=month_start,
        started_on__lte=today,
    ).filter(
        Exists(
            CustomerSubscription.objects.filter(
                customer_id=OuterRef('customer_id'),
                status=CustomerSubscription.Status.CANCELLED,
            ).annotate(
                churn_d=Coalesce(
                    'cancel_effective_on',
                    TruncDate('cancelled_at', tzinfo=BUSINESS_TZ),
                    output_field=DateField(),
                )
            ).filter(churn_d__lt=OuterRef('started_on'))
        )
    ).values('customer_id').distinct().count()

    return {
        'unsubscribed_this_month': unsubscribed_this_month,
        'churn_rate_this_month': churn_rate_this_month,
        'at_risk_count': at_risk_count,
        'won_back_this_month': won_back_this_month,
    }
