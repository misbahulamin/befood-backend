from django.db import transaction

from meals.models import MealCategory
from meals.services.pricing import calculate_per_meal_price
from orders.models import Order
from orders.services.order_duration import calculate_order_period

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


class OrderServiceError(Exception):
    pass


class MonthLockError(OrderServiceError):
    pass


class InactiveMealError(OrderServiceError):
    pass


class UnpricedMealError(OrderServiceError):
    pass


def check_existing_monthly_lock(customer, order_month: str) -> None:
    has_existing = Order.objects.filter(
        customer=customer,
        order_month=order_month,
        order_status__in=MONTH_LOCK_STATUSES,
    ).exists()
    if has_existing:
        raise MonthLockError(MONTH_LOCK_ERROR)


def prepare_snapshot_fields(meal: MealCategory, reference_date=None) -> dict:
    if meal.total_price is None:
        raise UnpricedMealError('This meal package has no published price yet. Finalize a cycle plan first.')
    per_meal_price = calculate_per_meal_price(meal.total_price, reference_date=reference_date)
    return {
        'meal_name_snapshot': meal.meal_name,
        'meal_type_snapshot': meal.meal_type,
        'total_price_snapshot': meal.total_price,
        'per_meal_price_snapshot': per_meal_price,
    }


@transaction.atomic
def create_meal_order(customer, meal: MealCategory, customer_note: str = '') -> Order:
    if not meal.is_active:
        raise InactiveMealError('This meal package is not available for ordering.')
    if meal.total_price is None:
        raise UnpricedMealError('This meal package has no published price yet. Finalize a cycle plan first.')

    period = calculate_order_period(meal.meal_type)
    check_existing_monthly_lock(customer, period.order_month)

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
    return order


def get_current_package(customer, reference_date=None):
    from django.utils import timezone

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
