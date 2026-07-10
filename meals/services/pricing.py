from calendar import monthrange
from decimal import Decimal

from django.utils import timezone


def get_present_month_days(reference_date=None):
    reference_date = reference_date or timezone.localdate()
    return monthrange(reference_date.year, reference_date.month)[1]


def calculate_per_meal_price(total_price, reference_date=None):
    days = get_present_month_days(reference_date)
    return (Decimal(total_price) / (days * 2)).quantize(Decimal('0.01'))
