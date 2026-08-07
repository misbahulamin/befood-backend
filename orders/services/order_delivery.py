from calendar import monthrange
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from meals.models import MealCategory
from meals.services.pricing import expected_servings, periods_for_meal_period, periods_per_day
from orders.models import Order, OrderDelivery
from orders.services.delivery_address import resolve_and_apply_snapshot
from orders.services.meal_payment import MealPaymentError, charge_delivered_meal
from orders.services.order_status import OrderStatusError, change_order_status

TERMINAL_DELIVERY_STATUSES = {
    OrderDelivery.DeliveryStatus.DELIVERED,
    OrderDelivery.DeliveryStatus.SKIPPED,
    OrderDelivery.DeliveryStatus.MISSED,
}

MARKABLE_STATUSES = {
    OrderDelivery.DeliveryStatus.DELIVERED,
    OrderDelivery.DeliveryStatus.SKIPPED,
}


class DeliveryError(Exception):
    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.code = code


def _daterange(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _resolve_meal_period(order: Order) -> str:
    period = getattr(order, 'meal_period_snapshot', None) or ''
    if period in ('lunch', 'dinner', 'both'):
        return period
    # Legacy fallback before snapshot existed.
    if order.meal_type_snapshot == MealCategory.MealType.DAILY:
        return MealCategory.MealPeriod.LUNCH
    return MealCategory.MealPeriod.BOTH


def expected_delivery_count(order: Order) -> int:
    meal_type = order.meal_type_snapshot
    meal_period = _resolve_meal_period(order)
    if meal_type == MealCategory.MealType.MONTHLY:
        year, month = map(int, order.order_month.split('-'))
        return expected_servings(meal_type, meal_period, year, month)
    days = (order.order_end_date - order.order_start_date).days + 1
    return days * periods_per_day(meal_period)


def _slot_specs_for_order(order: Order) -> list[tuple[date, str]]:
    meal_type = order.meal_type_snapshot
    meal_period = _resolve_meal_period(order)
    periods = periods_for_meal_period(meal_period)

    if meal_type == MealCategory.MealType.DAILY:
        return [(order.order_start_date, period) for period in periods]

    if meal_type == MealCategory.MealType.MONTHLY:
        year, month = map(int, order.order_month.split('-'))
        last_day = monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)
    else:
        start = order.order_start_date
        end = order.order_end_date

    slots: list[tuple[date, str]] = []
    for day in _daterange(start, end):
        for period in periods:
            slots.append((day, period))
    return slots


@transaction.atomic
def generate_order_deliveries(order: Order) -> list[OrderDelivery]:
    """Create expected delivery slots for an order. Idempotent for existing slots."""
    specs = _slot_specs_for_order(order)
    existing = {
        (d.service_date, d.meal_period)
        for d in order.deliveries.all()
    }
    customer = order.customer
    to_create = []
    for service_date, meal_period in specs:
        if (service_date, meal_period) in existing:
            continue
        delivery = OrderDelivery(
            order=order,
            service_date=service_date,
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )
        resolve_and_apply_snapshot(delivery, customer)
        to_create.append(delivery)
    if to_create:
        OrderDelivery.objects.bulk_create(to_create)
    return list(order.deliveries.order_by('service_date', 'meal_period', 'id'))


def get_order_progress(order: Order, reference_date: date | None = None) -> dict:
    today = reference_date or timezone.localdate()
    month_start = today.replace(day=1)
    last_day = monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day)

    aggregates = order.deliveries.aggregate(
        expected_count=Count('id'),
        delivered_count=Count('id', filter=Q(status=OrderDelivery.DeliveryStatus.DELIVERED)),
        remaining_count=Count('id', filter=Q(status=OrderDelivery.DeliveryStatus.SCHEDULED)),
    )
    expected = aggregates['expected_count'] or 0
    # Prefer computed expectation when slots not yet generated
    if expected == 0:
        expected = expected_delivery_count(order)

    active_days = list(
        order.deliveries.filter(
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
        'expected_deliveries': expected,
        'delivered_count': aggregates['delivered_count'] or 0,
        'remaining_count': aggregates['remaining_count'] or 0,
        'active_days_this_month': [d.isoformat() for d in active_days],
    }


def activate_order_if_due(order: Order, reference_date: date | None = None, changed_by=None) -> Order:
    today = reference_date or timezone.localdate()
    if order.order_status != Order.OrderStatus.CONFIRMED:
        return order
    if today < order.order_start_date:
        return order
    return change_order_status(
        order,
        Order.OrderStatus.ACTIVE,
        changed_by=changed_by,
        note='Auto-activated on or after start date.',
    )


def _all_deliveries_terminal(order: Order) -> bool:
    if not order.deliveries.exists():
        return False
    return not order.deliveries.filter(status=OrderDelivery.DeliveryStatus.SCHEDULED).exists()


def complete_order_if_done(order: Order, changed_by=None, note: str = '') -> Order:
    if order.order_status in {Order.OrderStatus.COMPLETED, Order.OrderStatus.CANCELLED}:
        return order

    meal_type = order.meal_type_snapshot
    should_complete = False
    completion_note = note

    if meal_type == MealCategory.MealType.DAILY:
        # Complete when every expected slot is terminal (delivered, skipped/meal-off, or missed).
        if _all_deliveries_terminal(order):
            should_complete = True
            completion_note = completion_note or 'Daily package completed; all slots terminal.'
    elif _all_deliveries_terminal(order):
        should_complete = True
        completion_note = completion_note or 'All delivery slots are terminal.'

    if not should_complete:
        return order

    if order.order_status == Order.OrderStatus.CONFIRMED:
        order = change_order_status(
            order,
            Order.OrderStatus.ACTIVE,
            changed_by=changed_by,
            note='Activated before completion.',
        )

    if order.order_status == Order.OrderStatus.ACTIVE:
        return change_order_status(
            order,
            Order.OrderStatus.COMPLETED,
            changed_by=changed_by,
            note=completion_note,
        )
    return order


def close_expired_order(order: Order, reference_date: date | None = None, changed_by=None) -> Order:
    today = reference_date or timezone.localdate()
    if order.order_status in {Order.OrderStatus.COMPLETED, Order.OrderStatus.CANCELLED}:
        return order
    if today <= order.order_end_date:
        return order

    order.deliveries.filter(status=OrderDelivery.DeliveryStatus.SCHEDULED).update(
        status=OrderDelivery.DeliveryStatus.MISSED,
        marked_at=timezone.now(),
        note='Marked missed after order end date.',
    )
    order = activate_order_if_due(order, reference_date=today, changed_by=changed_by)
    return complete_order_if_done(
        order,
        changed_by=changed_by,
        note='Completed after end date; remaining slots marked missed.',
    )


@transaction.atomic
def mark_delivery(
    delivery: OrderDelivery,
    to_status: str,
    marked_by=None,
    note: str = '',
) -> OrderDelivery:
    if to_status not in MARKABLE_STATUSES:
        raise DeliveryError(f'Cannot mark delivery as {to_status}. Use delivered or skipped.')

    locked = (
        OrderDelivery.objects.select_for_update()
        .select_related('order')
        .get(pk=delivery.pk)
    )
    order = locked.order

    if order.order_status == Order.OrderStatus.CANCELLED:
        raise DeliveryError('Cannot mark delivery on a cancelled order.')
    if order.order_status == Order.OrderStatus.COMPLETED and locked.status != to_status:
        raise DeliveryError('Cannot mark delivery on a completed order.')

    # Idempotent: same terminal status already set
    if locked.status == to_status:
        return locked

    if locked.status in TERMINAL_DELIVERY_STATUSES and locked.status != to_status:
        raise DeliveryError(
            f'Delivery is already {locked.status} and cannot change to {to_status}.'
        )

    activate_order_if_due(order, changed_by=marked_by)
    order.refresh_from_db()

    locked.status = to_status
    locked.marked_by = marked_by
    locked.marked_at = timezone.now()
    if note:
        locked.note = note
    update_fields = ['status', 'marked_by', 'marked_at', 'note', 'updated_at']
    if to_status == OrderDelivery.DeliveryStatus.SKIPPED:
        locked.skip_source = OrderDelivery.SkipSource.ADMIN
        update_fields.append('skip_source')
    locked.save(update_fields=update_fields)

    if to_status == OrderDelivery.DeliveryStatus.DELIVERED:
        try:
            charged = charge_delivered_meal(locked)
            if charged is not None:
                locked = charged
        except MealPaymentError as exc:
            raise DeliveryError(str(exc), code=exc.code) from exc
        try:
            from onahar.services.contribution import credit_for_delivery

            credit_for_delivery(locked, actor=marked_by)
        except Exception:
            # Never block meal delivery on charity processing failures; reconcile later.
            import logging

            logging.getLogger(__name__).exception(
                'Onahar credit_for_delivery failed for delivery_id=%s', locked.pk
            )

    order.refresh_from_db()
    try:
        complete_order_if_done(order, changed_by=marked_by)
    except OrderStatusError as exc:
        raise DeliveryError(str(exc)) from exc

    locked.refresh_from_db()
    return locked


@transaction.atomic
def sync_order_lifecycle(reference_date: date | None = None, changed_by=None) -> dict:
    today = reference_date or timezone.localdate()
    activated = 0
    completed = 0
    closed = 0

    due_confirmed = Order.objects.filter(
        order_status=Order.OrderStatus.CONFIRMED,
        order_start_date__lte=today,
    )
    for order in due_confirmed.iterator():
        before = order.order_status
        order = activate_order_if_due(order, reference_date=today, changed_by=changed_by)
        if order.order_status != before and order.order_status == Order.OrderStatus.ACTIVE:
            activated += 1

    expired = Order.objects.filter(
        order_status__in={Order.OrderStatus.CONFIRMED, Order.OrderStatus.ACTIVE},
        order_end_date__lt=today,
    )
    for order in expired.iterator():
        before = order.order_status
        order = close_expired_order(order, reference_date=today, changed_by=changed_by)
        if order.order_status == Order.OrderStatus.COMPLETED and before != Order.OrderStatus.COMPLETED:
            closed += 1
            completed += 1

    # Complete any active orders that already have all slots terminal
    for order in Order.objects.filter(order_status=Order.OrderStatus.ACTIVE).iterator():
        before = order.order_status
        order = complete_order_if_done(order, changed_by=changed_by)
        if (
            before == Order.OrderStatus.ACTIVE
            and order.order_status == Order.OrderStatus.COMPLETED
        ):
            completed += 1

    return {
        'activated': activated,
        'completed': completed,
        'closed_expired': closed,
        'reference_date': today.isoformat(),
    }
