"""Meal demand forecasting, kitchen ingredient requirements, and history snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from meals.services.slot_pricing import resolve_published_slot_for_delivery
from orders.models import MealDemandSnapshot, MealOffSettings, Order, OrderDelivery
from orders.services.meal_off import (
    get_meal_off_settings,
    meal_off_business_now,
    meal_off_deadline,
)

CONFIRMATION_ESTIMATED = 'estimated'
CONFIRMATION_CONFIRMED = 'confirmed'
KG_QUANTITY_PRECISION = Decimal('0.000001')


@dataclass
class PackageDemandRow:
    package_id: int
    package_public_id: str
    package_name: str
    total_customers: int
    expected_meal_count: int
    meal_off_count: int
    final_cooking_count: int


@dataclass
class DemandResult:
    service_date: date
    meal_period: str
    confirmation_status: str
    meal_off_deadline_at: datetime
    expected_meal_count: int
    meal_off_count: int
    final_cooking_count: int
    total_customers: int
    packages: list[PackageDemandRow] = field(default_factory=list)


@dataclass
class IngredientQty:
    ingredient_id: int
    ingredient_public_id: str
    name: str
    unit: str | None
    quantity: Decimal | None
    kg_per_person: Decimal | None
    quantity_available: bool


def confirmation_status(
    service_date: date,
    meal_period: str,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> str:
    settings_obj = settings_obj or get_meal_off_settings()
    now_local = now or meal_off_business_now(settings_obj)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=ZoneInfo(settings_obj.timezone))
    else:
        now_local = now_local.astimezone(ZoneInfo(settings_obj.timezone))
    deadline = meal_off_deadline(service_date, meal_period, settings_obj)
    if now_local > deadline:
        return CONFIRMATION_CONFIRMED
    return CONFIRMATION_ESTIMATED


def resolve_default_kitchen_slot(
    now: datetime | None = None,
    *,
    settings_obj: MealOffSettings | None = None,
) -> tuple[date, str]:
    """Today in meal-off TZ; lunch if local time < dinner_off_time, else dinner."""
    settings_obj = settings_obj or get_meal_off_settings()
    now_local = now or meal_off_business_now(settings_obj)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=ZoneInfo(settings_obj.timezone))
    else:
        now_local = now_local.astimezone(ZoneInfo(settings_obj.timezone))
    service_date = now_local.date()
    if now_local.time() < settings_obj.dinner_off_time:
        return service_date, OrderDelivery.MealPeriod.LUNCH
    return service_date, OrderDelivery.MealPeriod.DINNER


def _demand_queryset(
    service_date: date,
    meal_period: str,
    *,
    package_id: int | None = None,
    package_public_id: UUID | str | None = None,
):
    qs = (
        OrderDelivery.objects.filter(
            service_date=service_date,
            meal_period=meal_period,
        )
        .exclude(order__order_status=Order.OrderStatus.CANCELLED)
        .select_related('order', 'order__meal')
    )
    if package_id is not None:
        qs = qs.filter(order__meal_id=package_id)
    if package_public_id is not None:
        qs = qs.filter(order__meal__public_id=package_public_id)
    return qs


def get_demand(
    service_date: date,
    meal_period: str,
    *,
    package_id: int | None = None,
    package_public_id: UUID | str | None = None,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> DemandResult:
    settings_obj = settings_obj or get_meal_off_settings()
    qs = _demand_queryset(
        service_date,
        meal_period,
        package_id=package_id,
        package_public_id=package_public_id,
    )

    overall = qs.aggregate(
        expected=Count('id'),
        meal_off=Count('id', filter=Q(status=OrderDelivery.DeliveryStatus.SKIPPED)),
        customers=Count('order_id', distinct=True),
    )
    expected = int(overall['expected'] or 0)
    meal_off = int(overall['meal_off'] or 0)
    final = expected - meal_off
    total_customers = int(overall['customers'] or 0)

    package_rows: list[PackageDemandRow] = []
    package_agg = (
        qs.values(
            'order__meal_id',
            'order__meal__public_id',
            'order__meal__meal_name',
        )
        .annotate(
            expected=Count('id'),
            meal_off=Count('id', filter=Q(status=OrderDelivery.DeliveryStatus.SKIPPED)),
            customers=Count('order_id', distinct=True),
        )
        .order_by('order__meal__meal_name', 'order__meal_id')
    )
    for row in package_agg:
        pkg_expected = int(row['expected'] or 0)
        pkg_off = int(row['meal_off'] or 0)
        package_rows.append(
            PackageDemandRow(
                package_id=row['order__meal_id'],
                package_public_id=str(row['order__meal__public_id']),
                package_name=row['order__meal__meal_name'],
                total_customers=int(row['customers'] or 0),
                expected_meal_count=pkg_expected,
                meal_off_count=pkg_off,
                final_cooking_count=pkg_expected - pkg_off,
            )
        )

    deadline = meal_off_deadline(service_date, meal_period, settings_obj)
    return DemandResult(
        service_date=service_date,
        meal_period=meal_period,
        confirmation_status=confirmation_status(
            service_date, meal_period, now=now, settings_obj=settings_obj
        ),
        meal_off_deadline_at=deadline,
        expected_meal_count=expected,
        meal_off_count=meal_off,
        final_cooking_count=final,
        total_customers=total_customers,
        packages=package_rows,
    )


def _quantize_kg(value: Decimal) -> Decimal:
    return value.quantize(KG_QUANTITY_PRECISION, rounding=ROUND_HALF_UP)


def get_ingredient_requirements(
    demand: DemandResult,
) -> tuple[list[IngredientQty], bool]:
    """
    Build aggregated ingredient quantities for the demand slot.

    Returns (ingredients, ingredients_incomplete).
    Incomplete when any package with final_cooking_count > 0 lacks a published slot menu.
    """
    aggregates: dict[int, dict[str, Any]] = {}
    incomplete = False

    for pkg in demand.packages:
        if pkg.final_cooking_count <= 0:
            continue
        slot = resolve_published_slot_for_delivery(
            meal_id=pkg.package_id,
            service_date=demand.service_date,
            meal_period=demand.meal_period,
        )
        if slot is None:
            incomplete = True
            continue

        items = slot.items.select_related('ingredient').all()
        if not items:
            incomplete = True
            continue

        for item in items:
            ingredient = item.ingredient
            entry = aggregates.setdefault(
                ingredient.pk,
                {
                    'ingredient': ingredient,
                    'total_kg': Decimal('0'),
                    'kg_per_person': None,
                    'quantity_available': False,
                    'seen_without_qty': False,
                },
            )
            if ingredient.has_kg_pricing and ingredient.customers_per_kg:
                kg_per_person = _quantize_kg(
                    Decimal('1') / Decimal(ingredient.customers_per_kg)
                )
                entry['kg_per_person'] = kg_per_person
                entry['quantity_available'] = True
                entry['total_kg'] += _quantize_kg(
                    kg_per_person * Decimal(pkg.final_cooking_count)
                )
            else:
                entry['seen_without_qty'] = True

    results: list[IngredientQty] = []
    for entry in aggregates.values():
        ingredient = entry['ingredient']
        available = bool(entry['quantity_available'])
        quantity = _quantize_kg(entry['total_kg']) if available else None
        results.append(
            IngredientQty(
                ingredient_id=ingredient.pk,
                ingredient_public_id=str(ingredient.public_id),
                name=ingredient.name,
                unit='kg' if available else None,
                quantity=quantity,
                kg_per_person=entry['kg_per_person'],
                quantity_available=available,
            )
        )

    results.sort(key=lambda row: row.name.lower())
    return results, incomplete


def demand_to_dict(demand: DemandResult) -> dict[str, Any]:
    return {
        'service_date': demand.service_date.isoformat(),
        'meal_period': demand.meal_period,
        'confirmation_status': demand.confirmation_status,
        'meal_off_deadline_at': demand.meal_off_deadline_at.isoformat(),
        'total_customers': demand.total_customers,
        'expected_meal_count': demand.expected_meal_count,
        'meal_off_count': demand.meal_off_count,
        'final_cooking_count': demand.final_cooking_count,
        'remaining_meal_count': demand.final_cooking_count,
        'packages': [
            {
                'package_public_id': row.package_public_id,
                'package_name': row.package_name,
                'total_customers': row.total_customers,
                'expected_meal_count': row.expected_meal_count,
                'meal_off_count': row.meal_off_count,
                'final_cooking_count': row.final_cooking_count,
            }
            for row in demand.packages
        ],
    }


def ingredient_qty_to_dict(row: IngredientQty) -> dict[str, Any]:
    return {
        'ingredient_public_id': row.ingredient_public_id,
        'name': row.name,
        'unit': row.unit,
        'quantity': format(row.quantity, 'f') if row.quantity is not None else None,
        'kg_per_person': (
            format(row.kg_per_person, 'f') if row.kg_per_person is not None else None
        ),
        'quantity_available': row.quantity_available,
    }


def build_kitchen_requirement(
    service_date: date,
    meal_period: str,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
) -> dict[str, Any]:
    demand = get_demand(
        service_date,
        meal_period,
        now=now,
        settings_obj=settings_obj,
    )
    ingredients, incomplete = get_ingredient_requirements(demand)
    return {
        'service_date': demand.service_date.isoformat(),
        'meal_period': demand.meal_period,
        'confirmation_status': demand.confirmation_status,
        'expected_meal_count': demand.expected_meal_count,
        'meal_off_count': demand.meal_off_count,
        'final_cooking_count': demand.final_cooking_count,
        'total_customers': demand.total_customers,
        'ingredients_incomplete': incomplete,
        'ingredients': [ingredient_qty_to_dict(row) for row in ingredients],
    }


def _freeze_ingredients(ingredients: list[IngredientQty]) -> list[dict[str, Any]]:
    return [ingredient_qty_to_dict(row) for row in ingredients]


@transaction.atomic
def upsert_demand_snapshots_for_slot(
    service_date: date,
    meal_period: str,
    *,
    now: datetime | None = None,
    settings_obj: MealOffSettings | None = None,
    force: bool = False,
) -> list[MealDemandSnapshot]:
    """
    Upsert per-package snapshots for a confirmed (or force) slot.

    Skips write when status is still estimated unless force=True.
    """
    settings_obj = settings_obj or get_meal_off_settings()
    demand = get_demand(
        service_date,
        meal_period,
        now=now,
        settings_obj=settings_obj,
    )
    if demand.confirmation_status != CONFIRMATION_CONFIRMED and not force:
        return []

    captured_at = timezone.now()
    confirmed_at = (
        captured_at if demand.confirmation_status == CONFIRMATION_CONFIRMED else None
    )
    snapshots: list[MealDemandSnapshot] = []

    # Ingredients are computed for the whole slot; freeze the same aggregated list
    # on each package row for analysis, plus package-scoped counts.
    all_ingredients, _incomplete = get_ingredient_requirements(demand)

    for pkg in demand.packages:
        pkg_demand = DemandResult(
            service_date=demand.service_date,
            meal_period=demand.meal_period,
            confirmation_status=demand.confirmation_status,
            meal_off_deadline_at=demand.meal_off_deadline_at,
            expected_meal_count=pkg.expected_meal_count,
            meal_off_count=pkg.meal_off_count,
            final_cooking_count=pkg.final_cooking_count,
            total_customers=pkg.total_customers,
            packages=[pkg],
        )
        pkg_ingredients, _ = get_ingredient_requirements(pkg_demand)
        frozen = _freeze_ingredients(pkg_ingredients)

        snapshot, _created = MealDemandSnapshot.objects.update_or_create(
            service_date=service_date,
            meal_period=meal_period,
            package_id=pkg.package_id,
            defaults={
                'expected_meal_count': pkg.expected_meal_count,
                'meal_off_count': pkg.meal_off_count,
                'final_cooking_count': pkg.final_cooking_count,
                'total_customers': pkg.total_customers,
                'confirmation_status': demand.confirmation_status,
                'ingredient_requirements': frozen,
                'captured_at': captured_at,
                'confirmed_at': confirmed_at,
            },
        )
        snapshots.append(snapshot)

    # If no packages but we want a trail for empty confirmed days, skip (nothing to store).
    _ = all_ingredients
    return snapshots


def confirm_and_save_due_snapshots(
    *,
    reference_now: datetime | None = None,
    lookback_days: int = 7,
    settings_obj: MealOffSettings | None = None,
) -> dict[str, int]:
    """
    For recent service dates whose meal-off deadline has passed, upsert snapshots.
    """
    settings_obj = settings_obj or get_meal_off_settings()
    now_local = reference_now or meal_off_business_now(settings_obj)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=ZoneInfo(settings_obj.timezone))
    else:
        now_local = now_local.astimezone(ZoneInfo(settings_obj.timezone))

    today = now_local.date()
    start = today.fromordinal(today.toordinal() - lookback_days)
    end = today

    delivery_slots = (
        OrderDelivery.objects.filter(service_date__gte=start, service_date__lte=end)
        .exclude(order__order_status=Order.OrderStatus.CANCELLED)
        .values_list('service_date', 'meal_period')
        .distinct()
    )

    written = 0
    skipped_estimated = 0
    for service_date, meal_period in delivery_slots:
        status = confirmation_status(
            service_date, meal_period, now=now_local, settings_obj=settings_obj
        )
        if status != CONFIRMATION_CONFIRMED:
            skipped_estimated += 1
            continue
        rows = upsert_demand_snapshots_for_slot(
            service_date,
            meal_period,
            now=now_local,
            settings_obj=settings_obj,
        )
        written += len(rows)

    return {
        'written': written,
        'skipped_estimated': skipped_estimated,
        'lookback_days': lookback_days,
    }
