"""Admin Meal Close preset lists: today's meal-offs and low-balance cohort."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db.models import Q, QuerySet

from orders.models import OrderDelivery
from orders.services.meal_demand import (
    _low_balance_blocked_q,
    resolve_default_kitchen_slot,
)
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
from orders.services.order_wallet_settings import get_order_wallet_settings
from orders.services.subscription_parent import (
    delivery_customer,
    delivery_meal_name,
    live_delivery_q,
)
from orders.services.wallet_balance_thresholds import (
    customer_display_name,
    customer_phone,
    spendable_balance,
)
def meal_close_service_date():
    """Business today from meal-off settings timezone."""
    return meal_off_business_now(get_meal_off_settings()).date()


def resolve_meal_close_slot(
    *,
    service_date: date | None = None,
    meal_period: str | None = None,
) -> tuple[date, str]:
    """
    Resolve list slot. Omitted values use the same default kitchen slot
    (today + lunch before dinner_off_time, else dinner).
    """
    settings_obj = get_meal_off_settings()
    default_date, default_period = resolve_default_kitchen_slot(settings_obj=settings_obj)
    day = service_date or default_date
    period = meal_period or default_period
    return day, period


def today_meal_off_queryset(
    service_date: date | None = None,
    meal_period: str | None = None,
) -> QuerySet[OrderDelivery]:
    """
    Live skipped deliveries for a slot.

    Excludes low-balance blocked customers so Meal Close Meal Off matches
    kitchen customer_meal_off_count (disjoint from low-balance blocked).
    """
    day, period = resolve_meal_close_slot(
        service_date=service_date,
        meal_period=meal_period,
    )
    return (
        OrderDelivery.objects.select_related(
            'order',
            'order__customer__user',
            'order__meal',
            'subscription',
            'subscription__customer__user',
            'subscription__meal',
        )
        .filter(
            live_delivery_q(day),
            service_date=day,
            meal_period=period,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
        )
        .exclude(_low_balance_blocked_q())
        .order_by('id')
    )


def _meal_off_reason(delivery: OrderDelivery) -> str:
    source = (delivery.skip_source or '').strip()
    note = (delivery.note or '').strip()
    if source == OrderDelivery.SkipSource.CUSTOMER:
        label = 'Customer meal off'
    elif source == OrderDelivery.SkipSource.ADMIN:
        label = 'Admin meal off'
    elif source == OrderDelivery.SkipSource.SYSTEM:
        label = 'System meal off'
    elif source:
        label = source.replace('_', ' ').strip().capitalize()
    else:
        label = 'Meal off'
    if note:
        return f'{label}: {note}'
    return label


def serialize_meal_off_row(delivery: OrderDelivery) -> dict:
    customer = delivery_customer(delivery)
    return {
        'delivery_public_id': str(delivery.public_id),
        'order_public_id': str(delivery.order.public_id) if delivery.order_id else None,
        'subscription_public_id': (
            str(delivery.subscription.public_id) if delivery.subscription_id else None
        ),
        'customer_public_id': str(customer.public_id) if customer is not None else None,
        'customer_name': customer_display_name(customer) if customer is not None else None,
        'customer_phone': customer_phone(customer) if customer is not None else None,
        'customer_email': customer.user.email if customer is not None else None,
        'package_name': delivery_meal_name(delivery) or None,
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
        'status': delivery.status,
        'skip_source': delivery.skip_source,
        'note': delivery.note or None,
        'reason': _meal_off_reason(delivery),
    }


def build_meal_off_list(
    *,
    service_date: date | None = None,
    meal_period: str | None = None,
) -> dict:
    day, period = resolve_meal_close_slot(
        service_date=service_date,
        meal_period=meal_period,
    )
    rows = [
        serialize_meal_off_row(d)
        for d in today_meal_off_queryset(service_date=day, meal_period=period)
    ]
    return {
        'service_date': day.isoformat(),
        'meal_period': period,
        'count': len(rows),
        'results': rows,
    }


def slot_low_balance_deliveries(
    service_date: date,
    meal_period: str,
    threshold: Decimal,
) -> QuerySet[OrderDelivery]:
    """
    Live deliveries for the slot whose customer meal is affected by low balance:
    meal-stop blocked OR spendable balance below meal_stop_threshold.
    Having a live delivery implies an active package/subscription (or order) for the slot.
    """
    return (
        OrderDelivery.objects.select_related(
            'order',
            'order__customer__user',
            'order__customer__wallet',
            'order__meal',
            'subscription',
            'subscription__customer__user',
            'subscription__customer__wallet',
            'subscription__meal',
        )
        .filter(
            live_delivery_q(service_date),
            service_date=service_date,
            meal_period=meal_period,
        )
        .filter(
            Q(subscription__customer__meal_service_blocked_low_balance=True)
            | Q(order__customer__meal_service_blocked_low_balance=True)
            | Q(subscription__customer__wallet__balance__lt=threshold)
            | Q(order__customer__wallet__balance__lt=threshold)
        )
        .filter(
            Q(subscription__customer__is_email_verified=True, subscription__customer__user__is_active=True)
            | Q(order__customer__is_email_verified=True, order__customer__user__is_active=True)
        )
        .order_by('id')
    )


def serialize_low_balance_row_from_delivery(
    delivery: OrderDelivery,
    *,
    threshold: Decimal,
) -> dict:
    customer = delivery_customer(delivery)
    balance = spendable_balance(customer) if customer is not None else Decimal('0.00')
    blocked = bool(customer is not None and customer.meal_service_blocked_low_balance)
    return {
        'customer_public_id': str(customer.public_id) if customer is not None else '',
        'customer_name': customer_display_name(customer) if customer is not None else None,
        'customer_phone': customer_phone(customer) if customer is not None else None,
        'customer_email': customer.user.email if customer is not None else None,
        'package_name': delivery_meal_name(delivery) or None,
        'wallet_balance': f'{balance:.2f}',
        'meal_stop_threshold': f'{threshold:.2f}',
        'meal_service_blocked_low_balance': blocked,
        'meal_service_blocked_at': (
            customer.meal_service_blocked_at.isoformat()
            if customer is not None and customer.meal_service_blocked_at
            else None
        ),
        'meal_status': 'Blocked' if blocked else 'Low balance',
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
    }


def build_low_balance_list(
    *,
    service_date: date | None = None,
    meal_period: str | None = None,
) -> dict:
    """
    Slot-scoped low-balance cohort: customers with a live meal for the slot
    whose wallet / meal-stop state affects that meal.
    """
    day, period = resolve_meal_close_slot(
        service_date=service_date,
        meal_period=meal_period,
    )
    settings_obj = get_order_wallet_settings()
    threshold = Decimal(settings_obj.meal_stop_threshold).quantize(Decimal('0.01'))
    deliveries = slot_low_balance_deliveries(day, period, threshold)

    # One row per customer (first delivery if duplicates).
    seen: set[str] = set()
    rows: list[dict] = []
    for delivery in deliveries:
        customer = delivery_customer(delivery)
        if customer is None:
            continue
        key = str(customer.public_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            serialize_low_balance_row_from_delivery(delivery, threshold=threshold)
        )

    rows.sort(
        key=lambda r: (
            (r.get('customer_email') or ''),
            (r.get('customer_name') or ''),
        )
    )
    return {
        'service_date': day.isoformat(),
        'meal_period': period,
        'meal_stop_threshold': f'{threshold:.2f}',
        'count': len(rows),
        'results': rows,
    }


def parse_meal_close_date(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    return datetime.strptime(raw_value, '%Y-%m-%d').date()
