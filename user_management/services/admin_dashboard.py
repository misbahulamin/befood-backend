"""Admin ops dashboard summary aggregates (no Request objects)."""

from __future__ import annotations

from calendar import month_name
from datetime import time
from typing import Any

from orders.models import CustomerSubscription, OrderDelivery
from orders.services.meal_off import get_meal_off_settings, meal_off_business_now
from support.models import SupportConversation
from user_management.models import CustomerProfile
from user_management.services.admin_customer import customer_delivery_scope
from wallet.models import WalletTransaction

# Admin profile meal-status badge switches lunch → dinner at 14:00 business-local.
ADMIN_MEAL_STATUS_CUTOFF = time(14, 0)


def build_dashboard_summary() -> dict[str, Any]:
    """Return ops KPIs for the admin home dashboard in one round-trip."""
    settings_obj = get_meal_off_settings()
    now_local = meal_off_business_now(settings_obj)
    today = now_local.date()
    month_start = today.replace(day=1)
    delivered = OrderDelivery.DeliveryStatus.DELIVERED

    total_meals_served = OrderDelivery.objects.filter(status=delivered).count()
    monthly_meals_served = OrderDelivery.objects.filter(
        status=delivered,
        service_date__gte=month_start,
        service_date__lte=today,
    ).count()
    today_delivery = OrderDelivery.objects.filter(
        status=delivered,
        service_date=today,
    ).count()

    unread_support_count = SupportConversation.objects.filter(admin_unread_count__gt=0).count()
    pending_wallet_requests = WalletTransaction.objects.filter(
        type__in=[WalletTransaction.Type.RECHARGE, WalletTransaction.Type.WITHDRAW],
        status=WalletTransaction.Status.PENDING,
    ).count()

    return {
        'total_customers': CustomerProfile.objects.count(),
        'total_meals_served': total_meals_served,
        'monthly_meals_served': monthly_meals_served,
        'monthly_meals_label': f'{month_name[today.month]} Meals Served',
        'today_delivery': today_delivery,
        'active_subscribers': CustomerSubscription.objects.filter(
            status=CustomerSubscription.Status.ACTIVE,
        ).count(),
        'unread_support_count': unread_support_count,
        'pending_wallet_requests': pending_wallet_requests,
        'pending_actions': unread_support_count + pending_wallet_requests,
    }


def resolve_admin_meal_period(now_local_time: time) -> str:
    """Lunch before 14:00 business-local; dinner at or after 14:00."""
    if now_local_time < ADMIN_MEAL_STATUS_CUTOFF:
        return OrderDelivery.MealPeriod.LUNCH
    return OrderDelivery.MealPeriod.DINNER


def build_current_meal_status(customer: CustomerProfile) -> dict[str, Any] | None:
    """
    Compact current-slot meal ON/OFF for admin customer profile header.

    ON  = not skipped (scheduled / delivered / missed)
    OFF = status skipped (customer or admin meal-off)
    null if no delivery row exists for today's selected period.
    """
    settings_obj = get_meal_off_settings()
    now_local = meal_off_business_now(settings_obj)
    service_date = now_local.date()
    meal_period = resolve_admin_meal_period(now_local.time())

    delivery = (
        OrderDelivery.objects.filter(
            customer_delivery_scope(customer),
            service_date=service_date,
            meal_period=meal_period,
        )
        .order_by('-id')
        .first()
    )
    if delivery is None:
        return None

    is_on = delivery.status != OrderDelivery.DeliveryStatus.SKIPPED
    period_label = 'Lunch' if meal_period == OrderDelivery.MealPeriod.LUNCH else 'Dinner'
    state_label = 'On' if is_on else 'Off'

    return {
        'meal_period': meal_period,
        'is_on': is_on,
        'label': f'{period_label} {state_label}',
        'service_date': service_date.isoformat(),
    }
