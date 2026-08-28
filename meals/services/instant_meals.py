"""Instant Meal projections from published monthly menu slots."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.utils import timezone

from meals.models import (
    InstantMealSettings,
    MealCyclePlanLine,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from meals.services.cycle_calculations import (
    MONEY_PLACES,
    build_one_meal_price_preview,
    require_resolvable_ingredient_cost,
)
from meals.services.operational_cost import resolve_per_meal_operational_cost
from meals.services.plan_roles import plan_ingredient_role_map


ROLE_SORT_ORDER = {
    MealCyclePlanLine.ProductRole.MAIN: 0,
    MealCyclePlanLine.ProductRole.STAPLE: 1,
    MealCyclePlanLine.ProductRole.SIDE: 2,
    MealCyclePlanLine.ProductRole.SEASONING: 3,
    MealCyclePlanLine.ProductRole.OTHER: 4,
}

MEAL_PERIOD_SORT = {
    MonthlyMenuSlot.MealPeriod.LUNCH: 0,
    MonthlyMenuSlot.MealPeriod.DINNER: 1,
}


def get_instant_meal_settings() -> InstantMealSettings:
    return InstantMealSettings.load()


def update_instant_meal_settings(
    *,
    profit_percent: Decimal | None = None,
    duration_days: int | None = None,
) -> InstantMealSettings:
    settings_obj = InstantMealSettings.load()
    if profit_percent is not None:
        settings_obj.profit_percent = profit_percent
    if duration_days is not None:
        if duration_days not in InstantMealSettings.ALLOWED_DURATION_DAYS:
            raise ValidationError(
                {
                    'duration_days': (
                        'duration_days must be one of: '
                        f'{", ".join(str(d) for d in sorted(InstantMealSettings.ALLOWED_DURATION_DAYS))}.'
                    )
                }
            )
        settings_obj.duration_days = duration_days
    settings_obj.full_clean()
    settings_obj.save()
    return settings_obj


def resolve_instant_date_window(
    *,
    settings_obj: InstantMealSettings | None = None,
    reference_date: date | None = None,
) -> tuple[date, date]:
    """Inclusive local calendar window [today, today + duration_days - 1]."""
    settings_obj = settings_obj or get_instant_meal_settings()
    today = reference_date or timezone.localdate()
    end = today + timedelta(days=int(settings_obj.duration_days) - 1)
    return today, end


def instant_meal_public_id(*, package_public_id, service_date: date, meal_period: str) -> str:
    return f'{package_public_id}:{service_date.isoformat()}:{meal_period}'


def _slot_ingredients_ordered(slot: MonthlyMenuSlot, role_map: dict[int, str]) -> list:
    items = list(slot.items.all())

    def sort_key(item: MonthlyMenuSlotItem):
        role = role_map.get(item.ingredient_id) or MealCyclePlanLine.ProductRole.OTHER
        return (ROLE_SORT_ORDER.get(role, 99), item.ingredient.name.lower())

    items.sort(key=sort_key)
    return items


def _build_display_name(ordered_items: list[MonthlyMenuSlotItem]) -> str:
    names = [item.ingredient.name for item in ordered_items]
    return ' + '.join(names)


def compute_instant_slot_price(
    slot: MonthlyMenuSlot,
    *,
    profit_percent: Decimal,
) -> dict[str, Decimal] | None:
    """
    Compute Instant Meal price without mutating subscription snapshots.

    Returns None when the slot cannot be priced (skip card).
    """
    ingredients = [item.ingredient for item in slot.items.all()]
    if not ingredients:
        return None

    try:
        per_meal_op = resolve_per_meal_operational_cost(
            slot.service_date.year,
            slot.service_date.month,
        )
    except ValidationError:
        if slot.operational_cost_snapshot is not None:
            per_meal_op = Decimal(slot.operational_cost_snapshot)
        else:
            return None

    if slot.ingredient_cost_snapshot is not None:
        ingredient_cost = Decimal(slot.ingredient_cost_snapshot).quantize(MONEY_PLACES)
        try:
            for ingredient in ingredients:
                require_resolvable_ingredient_cost(ingredient)
        except ValidationError:
            # Snapshot locked at publish; still usable for Instant display.
            pass
        profit = (ingredient_cost * (Decimal(profit_percent) / Decimal('100'))).quantize(
            MONEY_PLACES
        )
        operational_cost = Decimal(per_meal_op).quantize(MONEY_PLACES)
        price = (ingredient_cost + operational_cost + profit).quantize(MONEY_PLACES)
        return {
            'ingredient_cost': ingredient_cost,
            'operational_cost': operational_cost,
            'profit': profit,
            'profit_percent': Decimal(profit_percent).quantize(MONEY_PLACES),
            'price': price,
        }

    try:
        preview = build_one_meal_price_preview(
            ingredients,
            per_meal_operational_cost=per_meal_op,
            profit_percent=profit_percent,
        )
    except ValidationError:
        return None

    return {
        'ingredient_cost': Decimal(preview['selected_ingredients_cost']).quantize(MONEY_PLACES),
        'operational_cost': Decimal(preview['per_meal_operational_cost']).quantize(MONEY_PLACES),
        'profit': Decimal(preview['profit']).quantize(MONEY_PLACES),
        'profit_percent': Decimal(preview['profit_percent']).quantize(MONEY_PLACES),
        'price': Decimal(preview['final_meal_price']).quantize(MONEY_PLACES),
    }


def _published_slots_in_window(start: date, end: date):
    return (
        MonthlyMenuSlot.objects.filter(
            schedule__status=MonthlyMenuSchedule.Status.PUBLISHED,
            service_date__gte=start,
            service_date__lte=end,
        )
        .select_related(
            'schedule',
            'schedule__plan',
            'schedule__plan__meal_category',
            'schedule__plan__cycle',
        )
        .prefetch_related(
            Prefetch(
                'items',
                queryset=MonthlyMenuSlotItem.objects.select_related('ingredient'),
            ),
            'schedule__plan__lines',
        )
        .order_by('service_date', 'meal_period', 'schedule__plan__meal_category__meal_name')
    )


def build_instant_meal_card(
    slot: MonthlyMenuSlot,
    *,
    profit_percent: Decimal,
) -> dict[str, Any] | None:
    package = slot.schedule.plan.meal_category
    role_map = plan_ingredient_role_map(slot.schedule.plan)
    ordered_items = _slot_ingredients_ordered(slot, role_map)
    if not ordered_items:
        return None

    pricing = compute_instant_slot_price(slot, profit_percent=profit_percent)
    if pricing is None:
        return None

    ingredients_payload = [
        {
            'name': item.ingredient.name,
            'product_role': role_map.get(item.ingredient_id),
        }
        for item in ordered_items
    ]

    image = None
    if package.meal_thumbnail:
        try:
            image = package.meal_thumbnail.url
        except ValueError:
            image = None

    subscriber_price = None
    if slot.final_meal_price_snapshot is not None:
        subscriber_price = str(
            Decimal(slot.final_meal_price_snapshot).quantize(MONEY_PLACES)
        )

    return {
        'public_id': instant_meal_public_id(
            package_public_id=package.public_id,
            service_date=slot.service_date,
            meal_period=slot.meal_period,
        ),
        'name': _build_display_name(ordered_items),
        'meal_period': slot.meal_period,
        'meal_type': slot.meal_period,
        'service_date': slot.service_date.isoformat(),
        'package_public_id': str(package.public_id),
        'package_source': str(package.public_id),
        'package_name': package.meal_name,
        'price': str(pricing['price']),
        'ingredient_cost': str(pricing['ingredient_cost']),
        'operational_cost': str(pricing['operational_cost']),
        'profit_percent': str(pricing['profit_percent']),
        'image': image,
        'subscriber_price': subscriber_price,
        'ingredients': ingredients_payload,
    }


def list_instant_meals(
    *,
    reference_date: date | None = None,
    settings_obj: InstantMealSettings | None = None,
) -> list[dict[str, Any]]:
    """
    Build Instant Meal cards for the admin-configured window.

    Unpriceable slots are skipped; the list never fails the whole response for one bad slot.
    Does not mutate subscription snapshots or cycle plan profit.
    """
    settings_obj = settings_obj or get_instant_meal_settings()
    start, end = resolve_instant_date_window(
        settings_obj=settings_obj,
        reference_date=reference_date,
    )
    profit_percent = Decimal(settings_obj.profit_percent)
    cards: list[dict[str, Any]] = []
    for slot in _published_slots_in_window(start, end):
        card = build_instant_meal_card(slot, profit_percent=profit_percent)
        if card is not None:
            cards.append(card)

    cards.sort(
        key=lambda c: (
            c['service_date'],
            MEAL_PERIOD_SORT.get(c['meal_period'], 99),
            c['package_name'].lower(),
            c['package_public_id'],
        )
    )
    return cards
