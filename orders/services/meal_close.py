"""Admin Meal Close preset lists: today's meal-offs and low-balance cohort."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, QuerySet

from orders.models import OrderDelivery
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
from orders.services.order_wallet_settings import get_order_wallet_settings
from orders.services.subscription_parent import delivery_customer, live_delivery_q
from orders.services.wallet_balance_thresholds import (
    customer_display_name,
    customer_phone,
    spendable_balance,
)
from user_management.models import CustomerProfile


def meal_close_service_date():
    """Business today from meal-off settings timezone."""
    return meal_off_business_now(get_meal_off_settings()).date()


def today_meal_off_queryset(service_date=None) -> QuerySet[OrderDelivery]:
    """Live deliveries for today with status=skipped."""
    day = service_date or meal_close_service_date()
    return (
        OrderDelivery.objects.select_related(
            'order',
            'order__customer__user',
            'subscription',
            'subscription__customer__user',
        )
        .filter(
            live_delivery_q(day),
            service_date=day,
            status=OrderDelivery.DeliveryStatus.SKIPPED,
        )
        .order_by('meal_period', 'id')
    )


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
        'service_date': delivery.service_date.isoformat(),
        'meal_period': delivery.meal_period,
        'status': delivery.status,
        'skip_source': delivery.skip_source,
        'note': delivery.note or None,
    }


def build_meal_off_list() -> dict:
    service_date = meal_close_service_date()
    rows = [serialize_meal_off_row(d) for d in today_meal_off_queryset(service_date)]
    return {
        'service_date': service_date.isoformat(),
        'count': len(rows),
        'results': rows,
    }


def low_balance_queryset(threshold: Decimal) -> QuerySet[CustomerProfile]:
    """
    Customers blocked for low balance, or spendable wallet below meal-stop threshold.
    Matches cron compare: balance < meal_stop_threshold.
    """
    return (
        CustomerProfile.objects.filter(
            Q(meal_service_blocked_low_balance=True) | Q(wallet__balance__lt=threshold),
            is_email_verified=True,
            user__is_active=True,
        )
        .select_related('user', 'wallet')
        .distinct()
        .order_by('user__email', 'id')
    )


def serialize_low_balance_row(customer: CustomerProfile) -> dict:
    balance = spendable_balance(customer)
    return {
        'customer_public_id': str(customer.public_id),
        'customer_name': customer_display_name(customer),
        'customer_phone': customer_phone(customer),
        'customer_email': customer.user.email,
        'wallet_balance': f'{balance:.2f}',
        'meal_service_blocked_low_balance': bool(customer.meal_service_blocked_low_balance),
        'meal_service_blocked_at': (
            customer.meal_service_blocked_at.isoformat()
            if customer.meal_service_blocked_at
            else None
        ),
    }


def build_low_balance_list() -> dict:
    settings_obj = get_order_wallet_settings()
    threshold = Decimal(settings_obj.meal_stop_threshold).quantize(Decimal('0.01'))
    rows = [serialize_low_balance_row(c) for c in low_balance_queryset(threshold)]
    return {
        'meal_stop_threshold': f'{threshold:.2f}',
        'count': len(rows),
        'results': rows,
    }
