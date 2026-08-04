"""Shared test helpers for meals app."""

from __future__ import annotations

from decimal import Decimal

from meals.models import OperationalCostItem, OperationalCostMonth


def ensure_operational_cost_month(
    year: int,
    month: int,
    *,
    target_meal_quantity: int = 10_000,
    items: list[tuple[str, Decimal]] | None = None,
) -> OperationalCostMonth:
    """
    Ensure an operational cost month exists for tests that call summary/finalize.

    Args:
        year: Calendar year.
        month: Calendar month.
        target_meal_quantity: Target meal volume (> 0).
        items: Optional list of (name, amount) pairs. Empty ledger when None.
    """
    cost_month, _ = OperationalCostMonth.objects.get_or_create(
        year=year,
        month=month,
        defaults={'target_meal_quantity': target_meal_quantity},
    )
    if cost_month.target_meal_quantity != target_meal_quantity:
        cost_month.target_meal_quantity = target_meal_quantity
        cost_month.save(update_fields=['target_meal_quantity', 'updated_at'])

    if items is not None:
        cost_month.items.all().delete()
        for index, (name, amount) in enumerate(items):
            OperationalCostItem.objects.create(
                month=cost_month,
                name=name,
                amount=amount,
                sort_order=index,
            )
    return cost_month
