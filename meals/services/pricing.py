from calendar import monthrange
from decimal import Decimal

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


def calculate_per_meal_price(total_price, reference_date=None):
    if total_price is None:
        return None
    days = get_present_month_days(reference_date)
    return (Decimal(total_price) / (days * 2)).quantize(Decimal('0.01'))
