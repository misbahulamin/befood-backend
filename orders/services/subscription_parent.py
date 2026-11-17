"""Resolve customer/meal parent for order- or subscription-owned deliveries."""

from __future__ import annotations

from datetime import date

from django.db.models import F, Q

from orders.models import CustomerSubscription, Order, OrderDelivery


def delivery_customer(delivery: OrderDelivery):
    if delivery.subscription_id:
        return delivery.subscription.customer
    if delivery.order_id:
        return delivery.order.customer
    if delivery.test_meal_order_id:
        return delivery.test_meal_order.customer
    return None


def delivery_meal(delivery: OrderDelivery):
    if delivery.subscription_id:
        return delivery.subscription.meal
    if delivery.order_id:
        return delivery.order.meal
    if delivery.test_meal_order_id:
        return delivery.test_meal_order.package
    return None


def delivery_meal_name(delivery: OrderDelivery) -> str:
    if delivery.subscription_id:
        return delivery.subscription.meal_name_snapshot
    if delivery.order_id:
        return delivery.order.meal_name_snapshot
    if delivery.test_meal_order_id:
        return (
            delivery.test_meal_order.package_name_snapshot
            or getattr(delivery.test_meal_order.package, 'meal_name', '')
        )
    return ''


def delivery_parent_is_cancelled(delivery: OrderDelivery) -> bool:
    """True when this slot should not be served or counted."""
    subscription = delivery.subscription
    if subscription is not None:
        if subscription.status != CustomerSubscription.Status.CANCELLED:
            return False
        if subscription.cancel_effective_on is None:
            return True
        return delivery.service_date > subscription.cancel_effective_on
    order = delivery.order
    if order is not None:
        return order.order_status == Order.OrderStatus.CANCELLED
    test_meal = delivery.test_meal_order
    if test_meal is not None:
        from orders.models import TestMealOrder

        return test_meal.order_status in (
            TestMealOrder.OrderStatus.CANCELLED,
            TestMealOrder.OrderStatus.FAILED,
        )
    return True


def live_delivery_q(service_date: date | None = None) -> Q:
    """
    Include historical non-cancelled order slots, subscription slots
    that are still in service, and countable Test Meal stops.
    """
    from orders.models import TestMealOrder

    historical = Q(order_id__isnull=False) & ~Q(
        order__order_status=Order.OrderStatus.CANCELLED
    )
    active_sub = Q(
        subscription_id__isnull=False,
        subscription__status=CustomerSubscription.Status.ACTIVE,
    )
    cancelled_serving = Q(
        subscription_id__isnull=False,
        subscription__status=CustomerSubscription.Status.CANCELLED,
        subscription__cancel_effective_on__isnull=False,
    )
    if service_date is not None:
        cancelled_serving &= Q(subscription__cancel_effective_on__gte=service_date)
    else:
        cancelled_serving &= Q(service_date__lte=F('subscription__cancel_effective_on'))
    test_meal_live = Q(
        test_meal_order_id__isnull=False,
    ) & ~Q(
        test_meal_order__order_status__in=(
            TestMealOrder.OrderStatus.CANCELLED,
            TestMealOrder.OrderStatus.FAILED,
        )
    )
    return historical | active_sub | cancelled_serving | test_meal_live
