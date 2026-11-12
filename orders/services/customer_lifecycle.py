"""
Shared customer subscription lifecycle classification (Asia/Dhaka).

Precedence (mutually exclusive):
  never_subscribed → unsubscribed → at_risk → won_back → active
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import (
    BooleanField,
    Case,
    Count,
    DateField,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest, Least, TruncDate
from django.utils import timezone

from meals.services.pricing import periods_per_day
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.meal_off import CUTOFF_PASSED_NOTE, get_meal_off_settings, meal_off_business_now
from orders.services.subscription_service import business_today, get_active_subscription

LIFECYCLE_NEVER_SUBSCRIBED = 'never_subscribed'
LIFECYCLE_UNSUBSCRIBED = 'unsubscribed'
LIFECYCLE_AT_RISK = 'at_risk'
LIFECYCLE_WON_BACK = 'won_back'
LIFECYCLE_ACTIVE = 'active'

LIFECYCLE_VALUES = frozenset(
    {
        LIFECYCLE_NEVER_SUBSCRIBED,
        LIFECYCLE_UNSUBSCRIBED,
        LIFECYCLE_AT_RISK,
        LIFECYCLE_WON_BACK,
        LIFECYCLE_ACTIVE,
    }
)

BUSINESS_TZ_NAME = 'Asia/Dhaka'
BUSINESS_TZ = ZoneInfo(BUSINESS_TZ_NAME)

AT_RISK_BLOCKED_DAYS_THRESHOLD = 3
AT_RISK_MEAL_OFF_DAYS_THRESHOLD = 5
AT_RISK_LOOKBACK_DAYS = 7
LEADING_SIGNAL_LOOKBACK_DAYS = 14

MONEY = Decimal('0.01')


def business_calendar_today(*, today: date | None = None) -> date:
    if today is not None:
        return today
    return business_today()


def to_business_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        value = timezone.make_aware(value, timezone=ZoneInfo('UTC'))
    return value.astimezone(BUSINESS_TZ).date()


def churn_date_for_subscription(subscription: CustomerSubscription) -> date | None:
    """Prefer cancel_effective_on; else Asia/Dhaka date of cancelled_at."""
    if subscription.cancel_effective_on is not None:
        return subscription.cancel_effective_on
    return to_business_date(subscription.cancelled_at)


def latest_churn_date_for_customer(customer, *, today: date | None = None) -> date | None:
    """Latest churn date among cancelled subscriptions (for unsubscribed customers)."""
    _ = today
    latest: date | None = None
    qs = customer.meal_subscriptions.filter(
        status=CustomerSubscription.Status.CANCELLED,
    ).only('cancel_effective_on', 'cancelled_at')
    for sub in qs:
        d = churn_date_for_subscription(sub)
        if d is not None and (latest is None or d > latest):
            latest = d
    return latest


def estimate_one_day_meal_cost(subscription: CustomerSubscription) -> Decimal | None:
    """
    Estimated one-day meal charge for the active subscription.

    Uses published package ``total_price`` averaged per calendar day for the
    package meal period, scaled to the subscription preference and quantity.
    Same rough source kitchen/wallet planning uses when slot prices are absent.
    """
    meal = getattr(subscription, 'meal', None)
    if meal is None or meal.total_price is None:
        return None
    try:
        settings_obj = get_meal_off_settings()
        today = meal_off_business_now(settings_obj).date()
    except Exception:
        today = timezone.localdate()
    from calendar import monthrange

    days = monthrange(today.year, today.month)[1]
    if days <= 0:
        return None
    package_periods = periods_per_day(meal.meal_period)
    pref_periods = periods_per_day(subscription.meal_period_snapshot)
    qty = max(int(getattr(subscription, 'quantity', 1) or 1), 1)
    # total_price covers package_periods per day for the month.
    per_day_full = Decimal(meal.total_price) / Decimal(days)
    scale = Decimal(pref_periods) / Decimal(package_periods)
    return (per_day_full * scale * qty).quantize(MONEY, rounding=ROUND_HALF_UP)


def _lookback_start(today: date, days: int) -> date:
    return today - timedelta(days=days - 1)


def count_low_balance_blocked_days(customer, *, today: date | None = None) -> int:
    """
    v1 approximation of low-balance blocked service days in the last 7 days.

    - If currently blocked: count Asia/Dhaka dates from blocked_at.date() through
      today inclusive, intersected with the last 7 service days.
    - Plus distinct service dates in the last 7 with SYSTEM skips noting cutoff_passed
      (resume-after-block path).
    """
    today = business_calendar_today(today=today)
    window_start = _lookback_start(today, AT_RISK_LOOKBACK_DAYS)
    blocked_dates: set[date] = set()

    if customer.meal_service_blocked_low_balance and customer.meal_service_blocked_at:
        blocked_from = to_business_date(customer.meal_service_blocked_at)
        if blocked_from is not None:
            start = max(blocked_from, window_start)
            d = start
            while d <= today:
                blocked_dates.add(d)
                d += timedelta(days=1)

    skip_dates = (
        OrderDelivery.objects.filter(
            subscription__customer_id=customer.pk,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            note=CUTOFF_PASSED_NOTE,
            service_date__gte=window_start,
            service_date__lte=today,
        )
        .values_list('service_date', flat=True)
        .distinct()
    )
    blocked_dates.update(skip_dates)
    return len(blocked_dates)


def count_meal_off_days(customer, *, today: date | None = None) -> int:
    """Distinct service dates in last 7 with customer/admin meal-off skips."""
    today = business_calendar_today(today=today)
    window_start = _lookback_start(today, AT_RISK_LOOKBACK_DAYS)
    return (
        OrderDelivery.objects.filter(
            subscription__customer_id=customer.pk,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source__in=(
                OrderDelivery.SkipSource.CUSTOMER,
                OrderDelivery.SkipSource.ADMIN,
            ),
            service_date__gte=window_start,
            service_date__lte=today,
        )
        .values('service_date')
        .distinct()
        .count()
    )


def is_wallet_below_one_day_cost(customer, subscription=None) -> bool:
    from orders.services.wallet_balance_thresholds import spendable_balance

    sub = subscription or get_active_subscription(customer)
    if sub is None:
        return False
    one_day = estimate_one_day_meal_cost(sub)
    if one_day is None:
        return False
    return spendable_balance(customer) < one_day


def is_at_risk(customer, *, today: date | None = None, subscription=None) -> bool:
    """True when an active subscriber meets any at-risk predicate."""
    sub = subscription or get_active_subscription(customer)
    if sub is None:
        return False
    today = business_calendar_today(today=today)
    if count_low_balance_blocked_days(customer, today=today) >= AT_RISK_BLOCKED_DAYS_THRESHOLD:
        return True
    if count_meal_off_days(customer, today=today) >= AT_RISK_MEAL_OFF_DAYS_THRESHOLD:
        return True
    if is_wallet_below_one_day_cost(customer, subscription=sub):
        return True
    return False


def has_won_back_history(customer, *, active_subscription=None) -> bool:
    """Active sub exists and an earlier cancelled sub churned before active.started_on."""
    active = active_subscription or get_active_subscription(customer)
    if active is None or active.started_on is None:
        return False
    for sub in customer.meal_subscriptions.filter(
        status=CustomerSubscription.Status.CANCELLED,
    ).only('cancel_effective_on', 'cancelled_at', 'started_on'):
        churn_d = churn_date_for_subscription(sub)
        if churn_d is not None and churn_d < active.started_on:
            return True
    return False


def classify_customer_lifecycle(customer, *, today: date | None = None) -> str:
    """Return exactly one lifecycle value for a customer."""
    today = business_calendar_today(today=today)
    has_any = customer.meal_subscriptions.exists()
    if not has_any:
        return LIFECYCLE_NEVER_SUBSCRIBED

    active = get_active_subscription(customer)
    if active is None:
        return LIFECYCLE_UNSUBSCRIBED

    if is_at_risk(customer, today=today, subscription=active):
        return LIFECYCLE_AT_RISK

    if has_won_back_history(customer, active_subscription=active):
        return LIFECYCLE_WON_BACK

    return LIFECYCLE_ACTIVE


def _active_subscription_qs():
    return CustomerSubscription.objects.filter(
        customer_id=OuterRef('pk'),
        status=CustomerSubscription.Status.ACTIVE,
    )


def _ever_subscription_qs():
    return CustomerSubscription.objects.filter(customer_id=OuterRef('pk'))


def at_risk_q(*, today: date | None = None) -> Q:
    """
    ORM Q matching customers who satisfy at-risk rules (requires active sub).

    Combines:
    - currently blocked spanning ≥3 of last 7 days
    - SYSTEM cutoff_passed skips on ≥3 distinct days in last 7
    - customer/admin meal-offs on ≥5 distinct days in last 7
    - spendable wallet balance < estimated one-day cost
    """
    today = business_calendar_today(today=today)
    window_start = _lookback_start(today, AT_RISK_LOOKBACK_DAYS)
    # blocked_at local date <= today - 2 ⇒ at least 3 inclusive days through today
    # currently blocked AND blocked_at date <= today-2 ⇒ ≥3 inclusive days through today
    blocked_long_enough = Q(
        meal_service_blocked_low_balance=True,
        meal_service_blocked_at__isnull=False,
        meal_service_blocked_at__date__lte=today - timedelta(days=2),
    )
    # If block started before the 7-day window, all 7 lookback days are blocked
    blocked_covers_window = Q(
        meal_service_blocked_low_balance=True,
        meal_service_blocked_at__isnull=False,
        meal_service_blocked_at__date__lt=window_start,
    )

    cutoff_skip_days = (
        OrderDelivery.objects.filter(
            subscription__customer_id=OuterRef('pk'),
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            note=CUTOFF_PASSED_NOTE,
            service_date__gte=window_start,
            service_date__lte=today,
        )
        .values('subscription__customer_id')
        .annotate(dcount=Count('service_date', distinct=True))
        .filter(dcount__gte=AT_RISK_BLOCKED_DAYS_THRESHOLD)
    )

    meal_off_days = (
        OrderDelivery.objects.filter(
            subscription__customer_id=OuterRef('pk'),
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source__in=(
                OrderDelivery.SkipSource.CUSTOMER,
                OrderDelivery.SkipSource.ADMIN,
            ),
            service_date__gte=window_start,
            service_date__lte=today,
        )
        .values('subscription__customer_id')
        .annotate(dcount=Count('service_date', distinct=True))
        .filter(dcount__gte=AT_RISK_MEAL_OFF_DAYS_THRESHOLD)
    )

    # Approximate one-day cost via meal.total_price / days_in_month * preference scale * qty
    from calendar import monthrange

    days = monthrange(today.year, today.month)[1]
    days_dec = Decimal(days)
    active_cost = (
        CustomerSubscription.objects.filter(
            customer_id=OuterRef('pk'),
            status=CustomerSubscription.Status.ACTIVE,
            meal__total_price__isnull=False,
        )
        .annotate(
            pref_periods=Case(
                When(meal_period_snapshot='both', then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            pkg_periods=Case(
                When(meal__meal_period='both', then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
        .annotate(
            one_day=ExpressionWrapper(
                F('meal__total_price')
                / Value(days_dec)
                * F('pref_periods')
                / F('pkg_periods')
                * F('quantity'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .filter(customer__wallet__balance__lt=F('one_day'))
    )

    return (
        Q(blocked_long_enough | blocked_covers_window)
        | Q(Exists(cutoff_skip_days))
        | Q(Exists(meal_off_days))
        | Q(Exists(active_cost))
    )


def won_back_exists_q() -> Exists:
    """Exists prior cancelled sub with churn_date < active.started_on."""
    active_started = Subquery(
        CustomerSubscription.objects.filter(
            customer_id=OuterRef(OuterRef('pk')),
            status=CustomerSubscription.Status.ACTIVE,
        ).values('started_on')[:1]
    )
    prior = CustomerSubscription.objects.filter(
        customer_id=OuterRef('pk'),
        status=CustomerSubscription.Status.CANCELLED,
    ).annotate(
        churn_d=Coalesce(
            'cancel_effective_on',
            TruncDate('cancelled_at', tzinfo=BUSINESS_TZ),
            output_field=DateField(),
        )
    ).filter(churn_d__lt=active_started)
    return Exists(prior)


def annotate_lifecycle(queryset: QuerySet, *, today: date | None = None) -> QuerySet:
    """
    Annotate CustomerProfile queryset with ``lifecycle`` (string) via Case/Exists.
    Does not loop customers in Python.
    """
    today = business_calendar_today(today=today)
    has_ever = Exists(_ever_subscription_qs())
    has_active = Exists(_active_subscription_qs())
    risk = at_risk_q(today=today)
    won = won_back_exists_q()

    qs = queryset.annotate(
        _has_ever_subscription=has_ever,
        _has_active_subscription=has_active,
    )
    qs = qs.annotate(
        _is_at_risk=Case(
            When(Q(_has_active_subscription=True) & risk, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        _is_won_back=Case(
            When(
                Q(_has_active_subscription=True) & ~risk & won,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )
    return qs.annotate(
        lifecycle=Case(
            When(_has_ever_subscription=False, then=Value(LIFECYCLE_NEVER_SUBSCRIBED)),
            When(_has_active_subscription=False, then=Value(LIFECYCLE_UNSUBSCRIBED)),
            When(_is_at_risk=True, then=Value(LIFECYCLE_AT_RISK)),
            When(_is_won_back=True, then=Value(LIFECYCLE_WON_BACK)),
            default=Value(LIFECYCLE_ACTIVE),
        ),
    )


def filter_by_lifecycle(
    queryset: QuerySet,
    lifecycle: str,
    *,
    today: date | None = None,
) -> QuerySet:
    if lifecycle not in LIFECYCLE_VALUES:
        raise ValueError(f'Unsupported lifecycle: {lifecycle}')
    annotated = annotate_lifecycle(queryset, today=today)
    return annotated.filter(lifecycle=lifecycle)


def churn_date_annotation_subquery():
    """Latest churn date for a customer (OuterRef pk = CustomerProfile)."""
    return Subquery(
        CustomerSubscription.objects.filter(
            customer_id=OuterRef('pk'),
            status=CustomerSubscription.Status.CANCELLED,
        )
        .annotate(
            churn_d=Coalesce(
                'cancel_effective_on',
                TruncDate('cancelled_at', tzinfo=BUSINESS_TZ),
                output_field=DateField(),
            )
        )
        .order_by('-cancel_effective_on', '-cancelled_at', '-pk')
        .values('churn_d')[:1],
        output_field=DateField(),
    )


def tenure_days_for_subscription(subscription: CustomerSubscription) -> int | None:
    """Days from started_on to churn_date inclusive-ish (started → churn)."""
    churn_d = churn_date_for_subscription(subscription)
    if churn_d is None or subscription.started_on is None:
        return None
    return max((churn_d - subscription.started_on).days, 0)


def month_bounds_dhaka(*, reference: date | None = None) -> tuple[date, date]:
    """Inclusive start and end of Asia/Dhaka calendar month containing reference."""
    today = business_calendar_today(today=reference)
    start = today.replace(day=1)
    from calendar import monthrange

    end = today.replace(day=monthrange(today.year, today.month)[1])
    return start, end
