"""Build orderable meal-month list for the customer month picker."""

from __future__ import annotations

from meals.services.package_menu import published_schedule_for_meal
from orders.models import Order
from orders.services.meal_month import (
    format_order_month,
    iter_orderable_months,
    month_label,
)
from orders.services.order_service import MONTH_LOCK_STATUSES


def build_orderable_months_for_meal(customer, meal, *, today=None) -> dict:
    months = []
    ordered_months = set(
        Order.objects.filter(
            customer=customer,
            order_status__in=MONTH_LOCK_STATUSES,
        ).values_list('order_month', flat=True)
    )

    for index, (year, month) in enumerate(iter_orderable_months(today=today)):
        order_month = format_order_month(year, month)
        months.append(
            {
                'year': year,
                'month': month,
                'order_month': order_month,
                'label': month_label(year, month),
                'is_current': index == 0,
                'is_published': published_schedule_for_meal(meal.id, year, month) is not None,
                'has_order': order_month in ordered_months,
            }
        )

    return {
        'meal_public_id': str(meal.public_id),
        'meal_name': meal.meal_name,
        'months': months,
    }
