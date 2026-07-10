from django.db import transaction

from orders.models import Order, OrderStatusHistory

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


@transaction.atomic
def change_order_status(order: Order, to_status: str, changed_by=None, note: str = '') -> Order:
    if to_status not in Order.OrderStatus.values:
        raise OrderStatusError(f'Invalid order status: {to_status}')

    allowed = ALLOWED_TRANSITIONS.get(order.order_status, set())
    if to_status not in allowed:
        raise OrderStatusError(
            f'Cannot change order status from {order.order_status} to {to_status}.'
        )

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
