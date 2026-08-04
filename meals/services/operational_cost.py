"""Monthly operational cost ledger totals and per-meal allocation."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from meals.models import OperationalCostMonth


MONEY_PLACES = Decimal('0.01')


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def total_operational_cost(month: OperationalCostMonth) -> Decimal:
    """Sum of item amounts for a month, quantized to money precision."""
    total = sum(
        (Decimal(item.amount) for item in month.items.all()),
        Decimal('0.00'),
    )
    return _quantize_money(total)


def per_meal_operational_cost_for_month(month: OperationalCostMonth) -> Decimal:
    """
    Compute per-meal operational cost for an existing month row.

    Args:
        month: Operational cost month with target_meal_quantity > 0.

    Returns:
        total_operational_cost / target_meal_quantity, quantized to 0.01.

    Raises:
        ValidationError: If target_meal_quantity is not greater than zero.
    """
    target = int(month.target_meal_quantity)
    if target <= 0:
        raise ValidationError(
            {
                'target_meal_quantity': (
                    'target_meal_quantity must be greater than 0 to compute '
                    'per-meal operational cost.'
                )
            }
        )
    return _quantize_money(total_operational_cost(month) / Decimal(target))


def resolve_per_meal_operational_cost(year: int, month: int) -> Decimal:
    """
    Resolve per-meal operational cost for a calendar year/month.

    Args:
        year: Calendar year.
        month: Calendar month 1-12.

    Returns:
        Quantized per-meal operational cost.

    Raises:
        ValidationError: When no OperationalCostMonth exists for the period
            or target_meal_quantity is invalid.
    """
    try:
        cost_month = OperationalCostMonth.objects.prefetch_related('items').get(
            year=year,
            month=month,
        )
    except OperationalCostMonth.DoesNotExist as exc:
        raise ValidationError(
            {
                'operational_cost_month': (
                    f'No operational cost month configured for {year}-{month:02d}. '
                    'Create an operational cost month with target_meal_quantity '
                    'before summary or finalize.'
                )
            }
        ) from exc

    if int(cost_month.target_meal_quantity) <= 0:
        raise ValidationError(
            {
                'target_meal_quantity': (
                    f'Operational cost month {year}-{month:02d} has invalid '
                    'target_meal_quantity; it must be greater than 0.'
                )
            }
        )

    return per_meal_operational_cost_for_month(cost_month)


def month_cost_breakdown(month: OperationalCostMonth) -> dict[str, Decimal]:
    """Return total and per-meal operational cost for API payloads."""
    total = total_operational_cost(month)
    per_meal = per_meal_operational_cost_for_month(month)
    return {
        'total_operational_cost': total,
        'per_meal_operational_cost': per_meal,
    }
