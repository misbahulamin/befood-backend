from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

from calendar import monthrange

from django.utils import timezone


def get_present_month_days(reference_date=None):
    reference_date = reference_date or timezone.localdate()
    return monthrange(reference_date.year, reference_date.month)[1]


def get_month_days(year: int, month: int) -> int:
    if month < 1 or month > 12:
        raise ValueError('Month must be between 1 and 12.')
    return monthrange(year, month)[1]


def total_meals_for_month(year: int, month: int, meals_per_day: int = 2) -> int:
    return get_month_days(year, month) * meals_per_day


def periods_per_day(meal_period: str) -> int:
    if meal_period == 'both':
        return 2
    if meal_period in ('lunch', 'dinner'):
        return 1
    raise ValueError(f'Unsupported meal period: {meal_period}')


def periods_for_meal_period(meal_period: str) -> list[str]:
    if meal_period == 'both':
        return ['lunch', 'dinner']
    if meal_period in ('lunch', 'dinner'):
        return [meal_period]
    raise ValueError(f'Unsupported meal period: {meal_period}')


def _add_months(reference_date: date, months: int) -> date:
    month_index = reference_date.month - 1 + months
    year = reference_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(reference_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def service_days_for_meal_type(meal_type: str, year: int, month: int) -> int:
    """Service-day counts aligned with order duration, anchored to year/month start for planning."""
    # Lazy import avoids circular import with MealCategory / order_duration.
    from meals.models import MealCategory

    if meal_type == MealCategory.MealType.DAILY:
        return 1
    if meal_type == MealCategory.MealType.WEEKLY:
        return 7
    if meal_type == MealCategory.MealType.HALF_MONTHLY:
        return 15
    if meal_type == MealCategory.MealType.MONTHLY:
        return get_month_days(year, month)
    if meal_type == MealCategory.MealType.SIX_MONTHS:
        start = date(year, month, 1)
        end = _add_months(start, 6) - timedelta(days=1)
        return (end - start).days + 1
    if meal_type == MealCategory.MealType.YEARLY:
        start = date(year, month, 1)
        end = _add_months(start, 12) - timedelta(days=1)
        return (end - start).days + 1
    raise ValueError(f'Unsupported meal type: {meal_type}')


def expected_servings(meal_type: str, meal_period: str, year: int, month: int) -> int:
    return service_days_for_meal_type(meal_type, year, month) * periods_per_day(meal_period)


def calculate_per_meal_price(total_price, meal_type, meal_period, reference_date=None):
    if total_price is None:
        return None
    reference_date = reference_date or timezone.localdate()
    servings = expected_servings(
        meal_type,
        meal_period,
        reference_date.year,
        reference_date.month,
    )
    if servings <= 0:
        raise ValueError('expected servings must be greater than 0.')
    return (Decimal(total_price) / Decimal(servings)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
