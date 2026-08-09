from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from meals.models import MealCategory
from meals.services.package_menu import published_schedule_for_meal
from meals.services.pricing import calculate_per_meal_price
from orders.models import Order
from orders.services.meal_month import (
    MENU_NOT_PUBLISHED_MESSAGE,
    MealMonthValidationError,
    assert_meal_month_in_window,
    resolve_optional_year_month,
)
from orders.services.order_delivery import generate_order_deliveries
from orders.services.order_duration import calculate_order_period
from orders.services.order_wallet_settings import get_order_wallet_settings

MONTH_LOCK_STATUSES = {
    Order.OrderStatus.PENDING,
    Order.OrderStatus.CONFIRMED,
    Order.OrderStatus.ACTIVE,
    Order.OrderStatus.COMPLETED,
}

MONTH_LOCK_ERROR = (
    'You already have a meal package for this month. '
    'You cannot change meal type within the same month.'
)

FROZEN_WALLET_ORDER_ERROR = (
    'Your wallet is frozen. You cannot place an order until it is unfrozen.'
)


class OrderServiceError(Exception):
    pass


class MonthLockError(OrderServiceError):
    pass


class InactiveMealError(OrderServiceError):
    pass


class UnpricedMealError(OrderServiceError):
    pass


class InsufficientWalletBalanceError(OrderServiceError):
    pass


class FrozenWalletOrderError(OrderServiceError):
    pass


class MenuNotPublishedError(OrderServiceError):
    pass


class InvalidMealMonthError(OrderServiceError):
    pass


class ServiceAreaOrderError(OrderServiceError):
    def __init__(self, message: str, code: str = 'SERVICE_AREA_UNAVAILABLE'):
        super().__init__(message)
        self.code = code


def check_existing_monthly_lock(customer, order_month: str) -> None:
    has_existing = Order.objects.filter(
        customer=customer,
        order_month=order_month,
        order_status__in=MONTH_LOCK_STATUSES,
    ).exists()
    if has_existing:
        raise MonthLockError(MONTH_LOCK_ERROR)


def check_wallet_min_balance(customer) -> None:
    """Require wallet balance >= configured minimum. Does not debit the wallet."""
    from wallet.models import Wallet

    settings_obj = get_order_wallet_settings()
    minimum = settings_obj.min_wallet_balance_to_order
    wallet = Wallet.objects.filter(customer=customer).first()
    if wallet is None:
        balance = Decimal('0.00')
        wallet_status = None
    else:
        balance = wallet.balance
        wallet_status = wallet.status

    if wallet_status == Wallet.Status.FROZEN:
        raise FrozenWalletOrderError(FROZEN_WALLET_ORDER_ERROR)

    if balance < minimum:
        raise InsufficientWalletBalanceError(
            f'Insufficient wallet balance to place an order. '
            f'Minimum required is {minimum}, current balance is {balance}.'
        )


def check_menu_published_for_meal_month(meal: MealCategory, year: int, month: int) -> None:
    if published_schedule_for_meal(meal.id, year, month) is None:
        raise MenuNotPublishedError(MENU_NOT_PUBLISHED_MESSAGE)


def prepare_snapshot_fields(meal: MealCategory, reference_date=None) -> dict:
    if meal.total_price is None:
        raise UnpricedMealError('This meal package has no published price yet. Finalize a cycle plan first.')
    per_meal_price = calculate_per_meal_price(
        meal.total_price,
        meal.meal_type,
        meal.meal_period,
        reference_date=reference_date,
    )
    return {
        'meal_name_snapshot': meal.meal_name,
        'meal_type_snapshot': meal.meal_type,
        'meal_period_snapshot': meal.meal_period,
        'total_price_snapshot': meal.total_price,
        'per_meal_price_snapshot': per_meal_price,
    }


def resolve_order_target_month(
    year: int | str | None = None,
    month: int | str | None = None,
    *,
    today=None,
) -> tuple[int, int]:
    """Return validated target (year, month), defaulting to current local month."""
    today = today or timezone.localdate()
    try:
        resolved = resolve_optional_year_month(year, month)
    except MealMonthValidationError as exc:
        raise InvalidMealMonthError(exc.message) from exc

    if resolved is None:
        return today.year, today.month

    target_year, target_month = resolved
    try:
        assert_meal_month_in_window(target_year, target_month, today=today)
    except MealMonthValidationError as exc:
        raise InvalidMealMonthError(exc.message) from exc
    return target_year, target_month


@transaction.atomic
def create_meal_order(
    customer,
    meal: MealCategory,
    customer_note: str = '',
    *,
    year: int | str | None = None,
    month: int | str | None = None,
) -> Order:
    if not meal.is_active:
        raise InactiveMealError('This meal package is not available for ordering.')
    if meal.total_price is None:
        raise UnpricedMealError('This meal package has no published price yet. Finalize a cycle plan first.')

    target_year, target_month = resolve_order_target_month(year, month)
    period = calculate_order_period(
        meal.meal_type,
        target_year=target_year,
        target_month=target_month,
    )
    check_menu_published_for_meal_month(meal, target_year, target_month)
    check_existing_monthly_lock(customer, period.order_month)
    check_wallet_min_balance(customer)

    from service_area.services.verification import (
        ServiceAreaError,
        assert_customer_order_serviceable,
    )

    try:
        assert_customer_order_serviceable(customer, meal.meal_period)
    except ServiceAreaError as exc:
        raise ServiceAreaOrderError(str(exc), code=exc.code) from exc

    snapshot = prepare_snapshot_fields(meal, reference_date=period.start_date)
    order = Order.objects.create(
        customer=customer,
        meal=meal,
        order_status=Order.OrderStatus.CONFIRMED,
        order_start_date=period.start_date,
        order_end_date=period.end_date,
        service_days_count=period.service_days_count,
        order_month=period.order_month,
        customer_note=customer_note or '',
        **snapshot,
    )
    generate_order_deliveries(order)
    return order


def get_current_package(customer, reference_date=None):
    today = reference_date or timezone.localdate()
    current_month = today.strftime('%Y-%m')
    return (
        Order.objects.filter(
            customer=customer,
            order_month=current_month,
        )
        .exclude(order_status=Order.OrderStatus.CANCELLED)
        .order_by('-created_at')
        .first()
    )
