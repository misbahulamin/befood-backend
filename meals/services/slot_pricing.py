"""Per lunch/dinner slot final selling price (publish-time snapshots)."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from meals.models import MonthlyMenuSchedule, MonthlyMenuSlot
from meals.services.cycle_calculations import (
    MONEY_PLACES,
    build_one_meal_price_preview,
    combined_unit_cost_per_customer,
)
from meals.services.operational_cost import resolve_per_meal_operational_cost


def compute_slot_final_price(
    slot: MonthlyMenuSlot,
    *,
    per_meal_operational_cost: Decimal,
    profit_percent: Decimal,
) -> dict:
    """
    Price one menu slot from its assigned ingredients.

    Returns decimal snapshots plus audit lines suitable for persistence.
    """
    ingredients = [item.ingredient for item in slot.items.select_related('ingredient').all()]
    if not ingredients:
        raise ValidationError(
            {
                'publish': (
                    f'Slot {slot.service_date.isoformat()} {slot.meal_period} has no ingredients.'
                )
            }
        )

    preview = build_one_meal_price_preview(
        ingredients,
        per_meal_operational_cost=per_meal_operational_cost,
        profit_percent=profit_percent,
    )
    return {
        'final_meal_price_snapshot': Decimal(preview['final_meal_price']),
        'ingredient_cost_snapshot': Decimal(preview['selected_ingredients_cost']).quantize(
            MONEY_PLACES
        ),
        'operational_cost_snapshot': Decimal(preview['per_meal_operational_cost']),
        'profit_snapshot': Decimal(preview['profit']),
        'ingredient_cost_lines': [
            {
                'public_id': str(ing.public_id),
                'name': ing.name,
                'unit_cost_per_customer': str(combined_unit_cost_per_customer(ing)),
            }
            for ing in ingredients
        ],
    }


def apply_price_snapshots_to_slot(slot: MonthlyMenuSlot, priced: dict) -> None:
    slot.final_meal_price_snapshot = priced['final_meal_price_snapshot']
    slot.ingredient_cost_snapshot = priced['ingredient_cost_snapshot']
    slot.operational_cost_snapshot = priced['operational_cost_snapshot']
    slot.profit_snapshot = priced['profit_snapshot']
    slot.ingredient_cost_lines = priced['ingredient_cost_lines']
    slot.save(
        update_fields=[
            'final_meal_price_snapshot',
            'ingredient_cost_snapshot',
            'operational_cost_snapshot',
            'profit_snapshot',
            'ingredient_cost_lines',
            'updated_at',
        ]
    )


def clear_slot_price_snapshots(slot: MonthlyMenuSlot) -> None:
    """Clear publish-locked prices so draft APIs show null until republish."""
    slot.final_meal_price_snapshot = None
    slot.ingredient_cost_snapshot = None
    slot.operational_cost_snapshot = None
    slot.profit_snapshot = None
    slot.ingredient_cost_lines = None
    slot.save(
        update_fields=[
            'final_meal_price_snapshot',
            'ingredient_cost_snapshot',
            'operational_cost_snapshot',
            'profit_snapshot',
            'ingredient_cost_lines',
            'updated_at',
        ]
    )


def snapshot_prices_for_schedule(schedule: MonthlyMenuSchedule) -> None:
    """
    Compute and persist final prices for every assigned slot on this schedule.

    Uses live catalog costs + plan profit + cycle-month operational cost at call time.
    Scoped only to ``schedule`` — never mutates sibling package schedules.
    """
    plan = schedule.plan
    cycle = plan.cycle
    per_meal_op = resolve_per_meal_operational_cost(cycle.year, cycle.month)
    profit_percent = plan.profit_percent

    slots = (
        schedule.slots.prefetch_related('items__ingredient')
        .order_by('service_date', 'meal_period')
        .all()
    )
    for slot in slots:
        if not slot.items.exists():
            continue
        priced = compute_slot_final_price(
            slot,
            per_meal_operational_cost=per_meal_op,
            profit_percent=profit_percent,
        )
        apply_price_snapshots_to_slot(slot, priced)


def clear_price_snapshots_for_schedule(schedule: MonthlyMenuSchedule) -> None:
    """Clear snapshots for all slots on this schedule only."""
    for slot in schedule.slots.all():
        clear_slot_price_snapshots(slot)


def resolve_published_slot_for_delivery(*, meal_id: int, service_date, meal_period: str):
    """Return the published menu slot for a package delivery, or None."""
    return (
        MonthlyMenuSlot.objects.filter(
            schedule__status=MonthlyMenuSchedule.Status.PUBLISHED,
            schedule__plan__meal_category_id=meal_id,
            schedule__plan__cycle__year=service_date.year,
            schedule__plan__cycle__month=service_date.month,
            service_date=service_date,
            meal_period=meal_period,
        )
        .select_related('schedule__plan')
        .first()
    )
