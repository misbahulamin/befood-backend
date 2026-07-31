from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from meals.models import MealCategory
from orders.services.meal_month import format_order_month


@dataclass(frozen=True)
class OrderPeriod:
    start_date: date
    end_date: date
    service_days_count: int
    order_month: str


def _add_months(reference_date: date, months: int) -> date:
    month_index = reference_date.month - 1 + months
    year = reference_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(reference_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def _inclusive_day_count(start_date: date, end_date: date) -> int:
    return (end_date - start_date).days + 1


def calculate_order_period(
    meal_type: str,
    reference_date: date | None = None,
    *,
    target_year: int | None = None,
    target_month: int | None = None,
) -> OrderPeriod:
    """
    Compute service window for a meal type.

    When target_year/target_month are set:
    - order_month is always that YYYY-MM
    - current month uses local today as reference (preserves mid-month daily/weekly)
    - future months use day 1 of the target month as reference
    """
    today = reference_date or timezone.localdate()

    stamped_order_month: str | None = None
    if target_year is not None and target_month is not None:
        stamped_order_month = format_order_month(target_year, target_month)
        if (target_year, target_month) == (today.year, today.month):
            effective = today
        else:
            effective = date(target_year, target_month, 1)
    else:
        effective = today

    if meal_type == MealCategory.MealType.DAILY:
        start_date = effective
        end_date = effective
        service_days_count = 1
    elif meal_type == MealCategory.MealType.WEEKLY:
        start_date = effective
        end_date = effective + timedelta(days=6)
        service_days_count = 7
    elif meal_type == MealCategory.MealType.HALF_MONTHLY:
        start_date = effective
        end_date = effective + timedelta(days=14)
        service_days_count = 15
    elif meal_type == MealCategory.MealType.MONTHLY:
        start_date = effective.replace(day=1)
        last_day = monthrange(effective.year, effective.month)[1]
        end_date = effective.replace(day=last_day)
        service_days_count = last_day
    elif meal_type == MealCategory.MealType.SIX_MONTHS:
        start_date = effective
        end_date = _add_months(effective, 6) - timedelta(days=1)
        service_days_count = _inclusive_day_count(start_date, end_date)
    elif meal_type == MealCategory.MealType.YEARLY:
        start_date = effective
        end_date = _add_months(effective, 12) - timedelta(days=1)
        service_days_count = _inclusive_day_count(start_date, end_date)
    else:
        raise ValueError(f'Unsupported meal type: {meal_type}')

    order_month = stamped_order_month or start_date.strftime('%Y-%m')
    return OrderPeriod(
        start_date=start_date,
        end_date=end_date,
        service_days_count=service_days_count,
        order_month=order_month,
    )
