"""One-off migration of in-flight monthly orders onto CustomerSubscription."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from orders.models import CustomerSubscription, Order, OrderDelivery
from orders.services.order_status import OrderStatusError, change_order_status
from orders.services.subscription_service import business_today


def _pick_source_order(orders: list[Order], today: date) -> Order | None:
    if not orders:
        return None
    current_month = f'{today.year:04d}-{today.month:02d}'
    for order in orders:
        if order.order_month == current_month:
            return order
    for order in orders:
        if order.order_end_date >= today:
            return order
    return orders[0]


@transaction.atomic
def migrate_in_flight_orders(*, today: date | None = None) -> dict:
    """
    Create one active subscription per customer from their current non-cancelled
    order, attach remaining slots from today forward, and cancel extra future-month
    orders. Customers who already have an active subscription are skipped.
    """
    today = today or business_today()
    now = timezone.now()
    created = 0
    skipped_existing = 0
    cancelled_extra = 0
    attached_slots = 0

    customer_ids = (
        Order.objects.exclude(order_status=Order.OrderStatus.CANCELLED)
        .values_list('customer_id', flat=True)
        .distinct()
    )

    for customer_id in customer_ids:
        if CustomerSubscription.objects.filter(
            customer_id=customer_id,
            status=CustomerSubscription.Status.ACTIVE,
        ).exists():
            skipped_existing += 1
            continue

        orders = list(
            Order.objects.filter(customer_id=customer_id)
            .exclude(order_status=Order.OrderStatus.CANCELLED)
            .select_related('meal', 'customer')
            .order_by('-order_month', '-created_at')
        )
        source = _pick_source_order(orders, today)
        if source is None:
            continue

        extras = [
            order
            for order in orders
            if order.pk != source.pk and order.order_month > source.order_month
        ]

        started_on = source.order_start_date or today
        subscription = CustomerSubscription.objects.create(
            customer_id=customer_id,
            meal_id=source.meal_id,
            meal_name_snapshot=source.meal_name_snapshot,
            meal_period_snapshot=source.meal_period_snapshot,
            status=CustomerSubscription.Status.ACTIVE,
            started_on=started_on,
            customer_note=source.customer_note or '',
        )
        attached_slots += OrderDelivery.objects.filter(
            order=source,
            service_date__gte=today,
            subscription__isnull=True,
        ).update(subscription=subscription)

        for extra in extras:
            extra.deliveries.filter(
                status=OrderDelivery.DeliveryStatus.SCHEDULED,
                service_date__gte=today,
            ).update(
                status=OrderDelivery.DeliveryStatus.SKIPPED,
                skip_source=OrderDelivery.SkipSource.SYSTEM,
                marked_at=now,
                note='Skipped after subscription migration of extra future-month order.',
            )
            try:
                change_order_status(
                    extra,
                    Order.OrderStatus.CANCELLED,
                    note='Cancelled extra future-month order during subscription migration.',
                )
            except OrderStatusError:
                extra.order_status = Order.OrderStatus.CANCELLED
                extra.save(update_fields=['order_status', 'updated_at'])
            cancelled_extra += 1

        created += 1

    return {
        'created': created,
        'skipped_existing': skipped_existing,
        'cancelled_extra': cancelled_extra,
        'attached_slots': attached_slots,
    }
