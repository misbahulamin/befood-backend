"""Customer meal subscription: subscribe, cancel, current entitlement."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from meals.models import MealCategory
from meals.services.package_menu import published_schedule_for_meal
from meals.services.pricing import periods_for_meal_period
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.delivery_address import resolve_and_apply_snapshot
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
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
) -> list[OrderDelivery]:
    """
    Idempotently create scheduled slots from started_on through the rolling horizon
    for months that have a published menu. Does not generate after cancel.
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


@transaction.atomic
def subscribe_customer(
    customer,
    meal: MealCategory,
    customer_note: str = '',
    *,
    today: date | None = None,
) -> CustomerSubscription:
    if not meal.is_active or not meal.is_subscribable:
        raise PlanUnavailableError(PLAN_UNAVAILABLE_ERROR)

    check_no_active_subscription(customer)
    check_subscribe_wallet(customer)

    started_on = today or business_today()
    subscription = CustomerSubscription.objects.create(
        customer=customer,
        meal=meal,
        meal_name_snapshot=meal.meal_name,
        meal_period_snapshot=meal.meal_period,
        status=CustomerSubscription.Status.ACTIVE,
        started_on=started_on,
        customer_note=customer_note or '',
    )
    ensure_subscription_deliveries(subscription, today=started_on)
    return subscription


@transaction.atomic
def cancel_subscription(
    subscription: CustomerSubscription,
    *,
    today: date | None = None,
) -> CustomerSubscription:
    locked = (
        CustomerSubscription.objects.select_for_update()
        .select_related('customer', 'meal')
        .get(pk=subscription.pk)
    )
    if locked.status == CustomerSubscription.Status.CANCELLED:
        return locked

    effective = today or business_today()
    locked.status = CustomerSubscription.Status.CANCELLED
    locked.cancelled_at = timezone.now()
    locked.cancel_effective_on = effective
    locked.save(
        update_fields=['status', 'cancelled_at', 'cancel_effective_on', 'updated_at']
    )

    locked.deliveries.filter(
        status=OrderDelivery.DeliveryStatus.SCHEDULED,
        service_date__gt=effective,
    ).update(
        status=OrderDelivery.DeliveryStatus.SKIPPED,
        skip_source=OrderDelivery.SkipSource.SYSTEM,
        marked_at=timezone.now(),
        note='Skipped after subscription cancel.',
    )
    locked.refresh_from_db()
    return locked


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
