from orders.services.order_status import ALLOWED_TRANSITIONS, OrderStatusError, change_order_status

ALLOWED = {
    from_status: set(to_statuses)
    for from_status, to_statuses in ALLOWED_TRANSITIONS.items()
}

TransitionError = OrderStatusError


def transition_order(order, to_status: str, changed_by=None, note=''):
    return change_order_status(order, to_status, changed_by=changed_by, note=note)
