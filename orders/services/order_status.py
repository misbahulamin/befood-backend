from django.db import transaction

from orders.models import Order, OrderDelivery, OrderStatusHistory

ALLOWED_TRANSITIONS = {
    Order.OrderStatus.PENDING: {
        Order.OrderStatus.CONFIRMED,
        Order.OrderStatus.ACTIVE,
        Order.OrderStatus.CANCELLED,
    },
    Order.OrderStatus.CONFIRMED: {
        Order.OrderStatus.ACTIVE,
        Order.OrderStatus.COMPLETED,
        Order.OrderStatus.CANCELLED,
    },
    Order.OrderStatus.ACTIVE: {
        Order.OrderStatus.COMPLETED,
        Order.OrderStatus.CANCELLED,
    },
    Order.OrderStatus.COMPLETED: set(),
    Order.OrderStatus.CANCELLED: set(),
}


class OrderStatusError(Exception):
    pass


def _apply_order_status(
    order: Order,
    to_status: str,
    *,
    changed_by=None,
    note: str = '',
) -> Order:
    from_status = order.order_status
    order.order_status = to_status
    order.save(update_fields=['order_status', 'updated_at'])
    OrderStatusHistory.objects.create(
        order=order,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        note=note,
    )
    return order


@transaction.atomic
def change_order_status(order: Order, to_status: str, changed_by=None, note: str = '') -> Order:
    if to_status not in Order.OrderStatus.values:
        raise OrderStatusError(f'Invalid order status: {to_status}')

    allowed = ALLOWED_TRANSITIONS.get(order.order_status, set())
    if to_status not in allowed:
        raise OrderStatusError(
            f'Cannot change order status from {order.order_status} to {to_status}.'
        )

    return _apply_order_status(order, to_status, changed_by=changed_by, note=note)


@transaction.atomic
def reopen_order_after_meal_on(order: Order, *, changed_by=None) -> Order:
    """
    Internal helper for customer meal-on only.

    When meal-off completed an order (all slots terminal), meal-on restores a
    scheduled slot and must reopen the order. Not exposed as a public status API.
    """
    locked = Order.objects.select_for_update().get(pk=order.pk)
    if locked.order_status != Order.OrderStatus.COMPLETED:
        return locked

    has_delivered = locked.deliveries.filter(
        status=OrderDelivery.DeliveryStatus.DELIVERED,
    ).exists()
    target = (
        Order.OrderStatus.ACTIVE
        if has_delivered
        else Order.OrderStatus.CONFIRMED
    )
    return _apply_order_status(
        locked,
        target,
        changed_by=changed_by,
        note='Reopened after customer meal-on.',
    )
