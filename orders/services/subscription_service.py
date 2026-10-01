"""Customer meal subscription: subscribe, cancel, current entitlement."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from meals.models import MealCategory
from meals.services.package_menu import published_schedule_for_meal
from meals.services.pricing import periods_for_meal_period
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.delivery_address import resolve_and_apply_snapshot
from orders.services.meal_off import (
    CUTOFF_PASSED_NOTE,
    get_meal_off_settings,
    is_past_meal_cutoff,
    meal_off_business_now,
)
from orders.services.order_service import (
    FrozenWalletOrderError,
    InactiveMealError,
    InsufficientWalletBalanceError,
    check_wallet_min_balance,
)
from orders.services.order_wallet_settings import get_order_wallet_settings

ALREADY_SUBSCRIBED_ERROR = 'You already have an active meal subscription.'
PLAN_UNAVAILABLE_ERROR = 'This meal plan is not available to subscribe.'
SUBSCRIBE_REQUIRED_ERROR = (
    'Monthly meal orders are retired. Subscribe to a meal plan instead.'
)
SUBSCRIBE_REQUIRED_CODE = 'SUBSCRIBE_REQUIRED'
FROZEN_WALLET_SUBSCRIBE_ERROR = (
    'Your wallet is frozen. You cannot subscribe until it is unfrozen.'
)


class SubscriptionError(Exception):
    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code


class PlanUnavailableError(SubscriptionError):
    pass


class AlreadySubscribedError(SubscriptionError):
    def __init__(self, message: str = ALREADY_SUBSCRIBED_ERROR):
        super().__init__(message, code='ALREADY_SUBSCRIBED')


class SubscribeRequiredError(SubscriptionError):
    def __init__(self, message: str = SUBSCRIBE_REQUIRED_ERROR):
        super().__init__(message, code=SUBSCRIBE_REQUIRED_CODE)


class SubscriptionNotFoundError(SubscriptionError):
    pass


class SubscriptionNotActiveError(SubscriptionError):
    pass


def business_today() -> date:
    settings_obj = get_meal_off_settings()
    return meal_off_business_now(settings_obj).date()


def rolling_horizon_end(today: date | None = None) -> date:
    today = today or business_today()
    if today.month == 12:
        next_year, next_month = today.year + 1, 1
    else:
        next_year, next_month = today.year, today.month + 1
    last_day = monthrange(next_year, next_month)[1]
    return date(next_year, next_month, last_day)


def get_active_subscription(customer) -> CustomerSubscription | None:
    return (
        CustomerSubscription.objects.filter(
            customer=customer,
            status=CustomerSubscription.Status.ACTIVE,
        )
        .select_related('meal', 'customer')
        .first()
    )


def check_no_active_subscription(customer) -> None:
    if get_active_subscription(customer) is not None:
        raise AlreadySubscribedError()


def check_subscribe_wallet(customer) -> None:
    """Reuse order wallet settings as the subscribe minimum. Does not debit."""
    try:
        check_wallet_min_balance(customer)
    except FrozenWalletOrderError as exc:
        raise FrozenWalletOrderError(FROZEN_WALLET_SUBSCRIBE_ERROR) from exc
    except InsufficientWalletBalanceError:
        settings_obj = get_order_wallet_settings()
        minimum = settings_obj.min_wallet_balance_to_order
        from wallet.models import Wallet

        wallet = Wallet.objects.filter(customer=customer).first()
        balance = Decimal('0.00') if wallet is None else wallet.balance
        raise InsufficientWalletBalanceError(
            f'Insufficient wallet balance to subscribe. '
            f'Minimum required is {minimum}, current balance is {balance}.'
        )


def _daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def ensure_subscription_deliveries(
    subscription: CustomerSubscription,
    *,
    through_date: date | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> list[OrderDelivery]:
    """
    Idempotently create delivery slots from started_on through the rolling horizon
    for months that have a published menu. Does not generate after cancel.

    New slots for the current business day whose meal-off cutoff has already passed
    are created as skipped (system / cutoff_passed). Existing rows are never updated.
    """
    if subscription.status != CustomerSubscription.Status.ACTIVE:
        return list(
            subscription.deliveries.order_by('service_date', 'meal_period', 'id')
        )

    today = today or business_today()
    through_date = through_date or rolling_horizon_end(today)
    start = max(subscription.started_on, today)
    if start > through_date:
        return list(
            subscription.deliveries.order_by('service_date', 'meal_period', 'id')
        )

    settings_obj = get_meal_off_settings()
    tz = ZoneInfo(settings_obj.timezone)
    raw_now = meal_off_business_now(settings_obj) if now is None else now
    if raw_now.tzinfo is None:
        now_local = raw_now.replace(tzinfo=tz)
    else:
        now_local = raw_now.astimezone(tz)
    business_day = now_local.date()

    periods = periods_for_meal_period(subscription.meal_period_snapshot)
    existing = {
        (row.service_date, row.meal_period)
        for row in subscription.deliveries.filter(
            service_date__gte=start,
            service_date__lte=through_date,
        )
    }
    published_months: dict[tuple[int, int], bool] = {}
    to_create: list[OrderDelivery] = []
    customer = subscription.customer

    for service_date in _daterange(start, through_date):
        key = (service_date.year, service_date.month)
        if key not in published_months:
            published_months[key] = (
                published_schedule_for_meal(
                    subscription.meal_id, service_date.year, service_date.month
                )
                is not None
            )
        if not published_months[key]:
            continue
        for meal_period in periods:
            slot_key = (service_date, meal_period)
            if slot_key in existing:
                continue
            past_cutoff = service_date == business_day and is_past_meal_cutoff(
                service_date,
                meal_period,
                now=now_local,
                settings_obj=settings_obj,
            )
            if past_cutoff:
                delivery = OrderDelivery(
                    order=None,
                    subscription=subscription,
                    service_date=service_date,
                    meal_period=meal_period,
                    status=OrderDelivery.DeliveryStatus.SKIPPED,
                    skip_source=OrderDelivery.SkipSource.SYSTEM,
                    note=CUTOFF_PASSED_NOTE,
                    marked_at=timezone.now(),
                )
            else:
                delivery = OrderDelivery(
                    order=None,
                    subscription=subscription,
                    service_date=service_date,
                    meal_period=meal_period,
                    status=OrderDelivery.DeliveryStatus.SCHEDULED,
                )
            resolve_and_apply_snapshot(delivery, customer)
            to_create.append(delivery)
            existing.add(slot_key)

    if to_create:
        OrderDelivery.objects.bulk_create(to_create)
    return list(subscription.deliveries.order_by('service_date', 'meal_period', 'id'))


def get_subscription_progress(
    subscription: CustomerSubscription,
    reference_date: date | None = None,
) -> dict:
    from django.db.models import Count, Q
    from calendar import monthrange as _monthrange

    today = reference_date or business_today()
    month_start = today.replace(day=1)
    last_day = _monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day)

    aggregates = subscription.deliveries.aggregate(
        expected_count=Count('id'),
        delivered_count=Count(
            'id', filter=Q(status=OrderDelivery.DeliveryStatus.DELIVERED)
        ),
        remaining_count=Count(
            'id', filter=Q(status=OrderDelivery.DeliveryStatus.SCHEDULED)
        ),
    )
    active_days = list(
        subscription.deliveries.filter(
            service_date__gte=month_start,
            service_date__lte=month_end,
            status__in={
                OrderDelivery.DeliveryStatus.SCHEDULED,
                OrderDelivery.DeliveryStatus.DELIVERED,
            },
        )
        .values_list('service_date', flat=True)
        .distinct()
        .order_by('service_date')
    )
    return {
        'expected_deliveries': aggregates['expected_count'] or 0,
        'delivered_count': aggregates['delivered_count'] or 0,
        'remaining_count': aggregates['remaining_count'] or 0,
        'active_days_this_month': [d.isoformat() for d in active_days],
    }


SUPPORTED_MEAL_PREFERENCES = frozenset({'lunch', 'dinner', 'both'})


def normalize_meal_preference(value: str | None) -> str:
    period = (value or '').strip().lower()
    if period not in SUPPORTED_MEAL_PREFERENCES:
        raise SubscriptionError(
            'meal_preference must be lunch, dinner, or both.',
            code='INVALID_MEAL_PREFERENCE',
        )
    return period


def resolve_effective_meal_period(
    meal: MealCategory,
    meal_preference: str | None,
    *,
    allow_fallback: bool = True,
) -> tuple[str, bool]:
    """Return (effective_period, used_fallback) for a subscribe/quote request.

    Package coverage is the upper bound: a both package may be narrowed to
    lunch or dinner; a single-period package cannot be broadened or switched.
    When meal_preference is omitted, the legacy package period is used so old
    clients keep their previous behavior during the compatibility window.
    """
    if meal_preference is None or str(meal_preference).strip() == '':
        if not allow_fallback:
            raise SubscriptionError(
                'meal_preference is required.',
                code='MEAL_PREFERENCE_REQUIRED',
            )
        return meal.meal_period, True
    preference = normalize_meal_preference(meal_preference)
    package_periods = set(periods_for_meal_period(meal.meal_period))
    selected_periods = set(periods_for_meal_period(preference))
    if not selected_periods.issubset(package_periods):
        raise SubscriptionError(
            f'{preference} is not available for this meal plan.',
            code='MEAL_PREFERENCE_NOT_SUPPORTED',
        )
    return preference, False


def normalize_subscription_quantity(value) -> int:
    from wallet.services.subscription_delivery_fee import normalize_quantity
    from wallet.services.subscription_delivery_fee import (
        SubscriptionDeliveryFeeError,
    )

    try:
        return normalize_quantity(value if value is not None else 1)
    except SubscriptionDeliveryFeeError as exc:
        raise SubscriptionError(str(exc), code='INVALID_QUANTITY') from exc


@transaction.atomic
def subscribe_customer(
    customer,
    meal: MealCategory,
    customer_note: str = '',
    *,
    today: date | None = None,
    meal_preference: str | None = None,
    quantity=None,
) -> CustomerSubscription:
    if not meal.is_active or not meal.is_subscribable:
        raise PlanUnavailableError(PLAN_UNAVAILABLE_ERROR)

    check_no_active_subscription(customer)
    check_subscribe_wallet(customer)

    effective_period, _used_fallback = resolve_effective_meal_period(
        meal, meal_preference, allow_fallback=True
    )
    canonical_quantity = normalize_subscription_quantity(
        quantity if quantity is not None else 1
    )

    started_on = today or business_today()
    subscription = CustomerSubscription.objects.create(
        customer=customer,
        meal=meal,
        meal_name_snapshot=meal.meal_name,
        meal_period_snapshot=effective_period,
        quantity=canonical_quantity,
        status=CustomerSubscription.Status.ACTIVE,
        started_on=started_on,
        customer_note=customer_note or '',
    )
    ensure_subscription_deliveries(subscription, today=started_on)
    return subscription


CANCEL_SKIP_NOTE = 'Skipped after subscription cancel.'


def classify_scheduled_for_cancel(
    deliveries,
    *,
    now: datetime | None = None,
    settings_obj=None,
) -> tuple[list[OrderDelivery], list[OrderDelivery]]:
    """
    Split SCHEDULED deliveries into (cancellable, preserved_finalized).

    Past meal-off cutoff (``is_past_meal_cutoff`` True) → preserve.
    At-or-before deadline → cancellable (soft-skip).
    Non-scheduled rows are ignored.
    """
    settings_obj = settings_obj or get_meal_off_settings()
    now_local = now or meal_off_business_now(settings_obj)
    cancellable: list[OrderDelivery] = []
    preserved: list[OrderDelivery] = []
    for delivery in deliveries:
        if delivery.status != OrderDelivery.DeliveryStatus.SCHEDULED:
            continue
        if is_past_meal_cutoff(
            delivery.service_date,
            delivery.meal_period,
            now=now_local,
            settings_obj=settings_obj,
        ):
            preserved.append(delivery)
        else:
            cancellable.append(delivery)
    return cancellable, preserved


def meal_summary_for_cancel(delivery: OrderDelivery) -> dict:
    """Serialize one meal row for cancel preview/response (includes charge estimate)."""
    from orders.services.meal_payment import estimate_delivery_charge

    return {
        'public_id': str(delivery.public_id),
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
        'estimated_charge': str(estimate_delivery_charge(delivery)),
    }


def build_cancel_classification_payload(
    subscription: CustomerSubscription,
    *,
    now: datetime | None = None,
) -> dict:
    """
    Read-only classification of SCHEDULED slots for cancel preview.

    Does not mutate subscription or delivery rows.
    """
    settings_obj = get_meal_off_settings()
    now_local = now or meal_off_business_now(settings_obj)
    scheduled = list(
        subscription.deliveries.filter(
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        ).order_by('service_date', 'meal_period', 'id')
    )
    cancellable, preserved = classify_scheduled_for_cancel(
        scheduled,
        now=now_local,
        settings_obj=settings_obj,
    )
    return {
        'cancelled_meals': [meal_summary_for_cancel(d) for d in cancellable],
        'preserved_finalized_meals': [meal_summary_for_cancel(d) for d in preserved],
    }


@transaction.atomic
def cancel_subscription(
    subscription: CustomerSubscription,
    *,
    today: date | None = None,
    cancelled_by=None,
    cancel_source: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> CustomerSubscription:
    """
    Canonical cancel: lock subscription, soft-skip cancellable SCHEDULED slots
    via meal-off cutoff classification, set cancelled status. Idempotent.
    """
    locked = (
        CustomerSubscription.objects.select_for_update()
        .select_related('customer', 'meal')
        .get(pk=subscription.pk)
    )
    if locked.status == CustomerSubscription.Status.CANCELLED:
        return locked

    settings_obj = get_meal_off_settings()
    now_local = now or meal_off_business_now(settings_obj)
    effective = today or business_today()

    scheduled = list(
        locked.deliveries.select_for_update(of=('self',)).filter(
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
    )
    cancellable, _preserved = classify_scheduled_for_cancel(
        scheduled,
        now=now_local,
        settings_obj=settings_obj,
    )
    if cancellable:
        marked_at = timezone.now()
        OrderDelivery.objects.filter(pk__in=[d.pk for d in cancellable]).update(
            status=OrderDelivery.DeliveryStatus.SKIPPED,
            skip_source=OrderDelivery.SkipSource.SYSTEM,
            marked_at=marked_at,
            note=CANCEL_SKIP_NOTE,
        )

    locked.status = CustomerSubscription.Status.CANCELLED
    locked.cancelled_at = timezone.now()
    locked.cancel_effective_on = effective
    update_fields = [
        'status',
        'cancelled_at',
        'cancel_effective_on',
        'updated_at',
    ]
    if cancelled_by is not None:
        locked.cancelled_by = cancelled_by
        update_fields.append('cancelled_by')
    if cancel_source:
        locked.cancel_source = cancel_source
        update_fields.append('cancel_source')
    # Optional reason is accepted for API symmetry; no dedicated field — leave customer_note.
    _ = reason
    locked.save(update_fields=update_fields)
    locked.refresh_from_db()
    return locked


def build_cancel_wallet_snapshot(customer, *, assume_cancelled: bool = False) -> dict:
    """
    Wallet figures for cancel preview/response.

    When ``assume_cancelled`` is True (preview before cancel, or after cancel),
    uses finalized-meal liability instead of the meal-stop threshold.
    """
    from orders.services.meal_payment import compute_finalized_meal_liability
    from orders.services.order_wallet_settings import get_order_wallet_settings
    from wallet.services.ledger import get_or_create_wallet
    from wallet.services.withdrawable import compute_maximum_withdrawable

    wallet = get_or_create_wallet(customer)
    settings_obj = get_order_wallet_settings()
    meal_stop = Decimal(settings_obj.meal_stop_threshold).quantize(Decimal('0.01'))
    has_active = get_active_subscription(customer) is not None
    if assume_cancelled:
        has_active = False
    liability = Decimal('0.00')
    if not has_active:
        liability = compute_finalized_meal_liability(customer)
    withdrawable = compute_maximum_withdrawable(
        wallet.recharge_balance,
        meal_stop,
        has_active_subscription=has_active,
        finalized_meal_liability=liability,
    )
    return {
        'balance': str(wallet.balance.quantize(Decimal('0.01'))),
        'recharge_balance': str(wallet.recharge_balance.quantize(Decimal('0.01'))),
        'meal_stop_threshold': str(meal_stop),
        'finalized_meal_liability': str(liability),
        'withdrawable_balance': str(withdrawable),
    }


def build_subscription_cancel_response(
    subscription: CustomerSubscription,
    *,
    cancelled_meals: list[dict] | None = None,
    preserved_finalized_meals: list[dict] | None = None,
    now: datetime | None = None,
    assume_cancelled: bool = False,
) -> dict:
    """Full admin cancel / preview response body."""
    if cancelled_meals is None or preserved_finalized_meals is None:
        classification = build_cancel_classification_payload(subscription, now=now)
        cancelled_meals = classification['cancelled_meals']
        preserved_finalized_meals = classification['preserved_finalized_meals']

    cancelled_by_payload = None
    if subscription.cancelled_by_id:
        actor = subscription.cancelled_by
        cancelled_by_payload = {
            'id': actor.pk,
            'email': actor.email,
        }

    # After cancel (or preview of cancel) wallet uses liability formula.
    post_cancel = assume_cancelled or (
        subscription.status == CustomerSubscription.Status.CANCELLED
    )

    return {
        'subscription': {
            'public_id': str(subscription.public_id),
            'status': subscription.status,
            'cancelled_at': (
                subscription.cancelled_at.isoformat()
                if subscription.cancelled_at
                else None
            ),
            'cancel_effective_on': (
                subscription.cancel_effective_on.isoformat()
                if subscription.cancel_effective_on
                else None
            ),
            'cancel_source': subscription.cancel_source,
            'cancelled_by': cancelled_by_payload,
        },
        'cancelled_meals': cancelled_meals,
        'preserved_finalized_meals': preserved_finalized_meals,
        'wallet': build_cancel_wallet_snapshot(
            subscription.customer,
            assume_cancelled=post_cancel,
        ),
    }


def ensure_all_active_subscription_deliveries(*, today: date | None = None) -> int:
    """Cron/post-publish: ensure slots for every active subscription. Returns count processed."""
    today = today or business_today()
    count = 0
    qs = CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE
    ).select_related('meal', 'customer')
    for subscription in qs.iterator():
        ensure_subscription_deliveries(subscription, today=today)
        count += 1
    return count
