from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from meals.models import Ingredient, MealCyclePlan, MealCyclePlanLine
from meals.services.meal_offering import publish_meal_price_from_plan
from meals.services.operational_cost import resolve_per_meal_operational_cost
from meals.services.plan_roles import MAIN_ROLE
from meals.services.pricing import expected_servings


MONEY_PLACES = Decimal('0.01')
COST_PLACES = Decimal('0.000001')


def _quantize(value: Decimal, places: Decimal = MONEY_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _published_price_sync_status(
    total_cost: Decimal,
    published_price: Decimal | None,
) -> tuple[str, str | None]:
    if published_price is None:
        return 'in_sync', None
    total_q = _quantize(Decimal(total_cost))
    published_q = _quantize(Decimal(published_price))
    if total_q == published_q:
        return 'in_sync', None
    return 'stale', str(_quantize(total_q - published_q))


def _realized_profit_margin_percent(
    *,
    published_price: Decimal,
    product_cost: Decimal,
    other_cost: Decimal,
) -> str | None:
    if product_cost <= 0:
        return None
    realized_profit = _quantize(published_price - product_cost - other_cost)
    margin = (realized_profit / product_cost * Decimal('100')).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )
    return str(margin)


def plan_expected_servings(plan: MealCyclePlan) -> int:
    meal = plan.meal_category
    return expected_servings(
        meal.meal_type,
        meal.meal_period,
        plan.cycle.year,
        plan.cycle.month,
    )


def ingredient_has_resolvable_cost(ingredient: Ingredient) -> bool:
    return ingredient.has_kg_pricing or ingredient.cost_per_customer is not None


def require_resolvable_ingredient_cost(ingredient: Ingredient) -> None:
    if ingredient_has_resolvable_cost(ingredient):
        return
    raise ValidationError(
        {
            'ingredient': (
                f'Ingredient "{ingredient.name}" has no resolvable cost. '
                'Provide kg pricing (price_per_kg and customers_per_kg) '
                'or a flat cost_per_customer before using it on a plan.'
            )
        }
    )


def assert_plan_ingredients_have_resolvable_cost(plan: MealCyclePlan) -> None:
    missing = [
        line.ingredient.name
        for line in plan.lines.select_related('ingredient').all()
        if not ingredient_has_resolvable_cost(line.ingredient)
    ]
    if not missing:
        return
    names = ', '.join(missing)
    raise ValidationError(
        {
            'ingredient': (
                f'These ingredients have no resolvable cost: {names}. '
                'Provide kg pricing or cost_per_customer.'
            )
        }
    )


def resolved_kg_cost_per_customer(ingredient: Ingredient) -> Decimal | None:
    """Kg-only unit cost (`price_per_kg / customers_per_kg`), or None when no kg pair."""
    if not ingredient.has_kg_pricing:
        return None
    return _quantize(
        Decimal(ingredient.price_per_kg) / Decimal(ingredient.customers_per_kg),
        COST_PLACES,
    )


def flat_cost_contribution(ingredient: Ingredient) -> Decimal:
    """Flat cooking/piece cost contribution; null stored cost counts as 0 in the sum."""
    if ingredient.cost_per_customer is None:
        return Decimal('0')
    return Decimal(ingredient.cost_per_customer)


def combined_unit_cost_per_customer(ingredient: Ingredient) -> Decimal:
    """Additive unit cost: (resolved_kg or 0) + (flat or 0)."""
    kg = resolved_kg_cost_per_customer(ingredient) or Decimal('0')
    return _quantize(kg + flat_cost_contribution(ingredient), COST_PLACES)


def resolve_cost_per_customer(ingredient: Ingredient) -> Decimal:
    """Kg-only resolved unit cost. Prefer resolved_kg_cost_per_customer for nullable reads."""
    kg = resolved_kg_cost_per_customer(ingredient)
    if kg is None:
        raise ValidationError(
            {
                'ingredient': (
                    f'Ingredient "{ingredient.name}" has no kilogram pricing. '
                    'Provide price_per_kg and customers_per_kg for resolved_cost_per_customer.'
                )
            }
        )
    return kg


def calculate_line_product_cost(unit_cost: Decimal, servings_count: int) -> Decimal:
    return _quantize(Decimal(unit_cost) * Decimal(servings_count), MONEY_PLACES)


def calculate_estimated_kg(servings_count: int, customers_per_kg: Decimal | None) -> Decimal | None:
    if customers_per_kg is None or customers_per_kg <= 0:
        return None
    return _quantize(Decimal(servings_count) / Decimal(customers_per_kg), Decimal('0.01'))


def build_line_detail(line: MealCyclePlanLine) -> dict:
    ingredient = line.ingredient
    resolved = resolved_kg_cost_per_customer(ingredient)
    flat = ingredient.cost_per_customer
    combined = combined_unit_cost_per_customer(ingredient)
    line_product_cost = calculate_line_product_cost(combined, line.servings_count)
    estimated_kg = calculate_estimated_kg(line.servings_count, ingredient.customers_per_kg)
    return {
        'id': line.id,
        'ingredient_id': ingredient.id,
        'ingredient_name': ingredient.name,
        'product_role': line.product_role,
        'servings_count': line.servings_count,
        'resolved_cost_per_customer': str(resolved) if resolved is not None else None,
        'cost_per_customer': (
            str(_quantize(Decimal(flat), COST_PLACES)) if flat is not None else None
        ),
        'line_product_cost': str(line_product_cost),
        'estimated_kg': str(estimated_kg) if estimated_kg is not None else None,
        'price_per_kg': str(ingredient.price_per_kg) if ingredient.price_per_kg is not None else None,
        'customers_per_kg': (
            str(ingredient.customers_per_kg) if ingredient.customers_per_kg is not None else None
        ),
    }


def calculate_package_totals(
    product_cost: Decimal,
    per_meal_operational_cost: Decimal,
    profit_percent: Decimal,
    expected_servings_count: int,
) -> dict[str, Decimal]:
    """
    Roll up package costs using absolute operational allocation.

    other_cost = expected_servings × per_meal_operational_cost
    profit = product_cost × profit_percent / 100
    """
    if expected_servings_count <= 0:
        raise ValidationError('expected_servings must be greater than 0.')
    other_cost = _quantize(
        Decimal(expected_servings_count) * Decimal(per_meal_operational_cost)
    )
    profit = _quantize(product_cost * (Decimal(profit_percent) / Decimal('100')))
    total_cost = _quantize(product_cost + other_cost + profit)
    per_meal_rate = _quantize(total_cost / Decimal(expected_servings_count))
    return {
        'product_cost': _quantize(product_cost),
        'other_cost': other_cost,
        'profit': profit,
        'total_cost': total_cost,
        'per_meal_rate': per_meal_rate,
        'per_meal_operational_cost': _quantize(Decimal(per_meal_operational_cost)),
    }


def build_one_meal_price_preview(
    ingredients: list[Ingredient],
    *,
    per_meal_operational_cost: Decimal,
    profit_percent: Decimal,
) -> dict:
    """Single-serving admin cost preview from selected ingredients."""
    for ingredient in ingredients:
        require_resolvable_ingredient_cost(ingredient)

    selected_cost = sum(
        (combined_unit_cost_per_customer(ingredient) for ingredient in ingredients),
        Decimal('0'),
    )
    selected_cost = _quantize(selected_cost, COST_PLACES)
    other_one = _quantize(Decimal(per_meal_operational_cost))
    profit_one = _quantize(selected_cost * (Decimal(profit_percent) / Decimal('100')))
    final_price = _quantize(selected_cost + other_one + profit_one)
    return {
        'selected_ingredients_cost': str(_quantize(selected_cost)),
        'per_meal_operational_cost': str(other_one),
        'profit_percent': str(_quantize(Decimal(profit_percent))),
        'profit': str(profit_one),
        'final_meal_price': str(final_price),
        'ingredients': [
            {
                'public_id': str(ingredient.public_id),
                'name': ingredient.name,
                'unit_cost_per_customer': str(combined_unit_cost_per_customer(ingredient)),
            }
            for ingredient in ingredients
        ],
    }


def build_plan_cost_preview(plan: MealCyclePlan, ingredients: list[Ingredient]) -> dict:
    per_meal_op = resolve_per_meal_operational_cost(plan.cycle.year, plan.cycle.month)
    preview = build_one_meal_price_preview(
        ingredients,
        per_meal_operational_cost=per_meal_op,
        profit_percent=plan.profit_percent,
    )
    preview['plan_public_id'] = str(plan.public_id)
    preview['cycle'] = {
        'year': plan.cycle.year,
        'month': plan.cycle.month,
    }
    return preview


def build_plan_summary(plan: MealCyclePlan, *, use_snapshot: bool | None = None) -> dict:
    use_snapshot = plan.is_finalized if use_snapshot is None else use_snapshot
    assert_plan_ingredients_have_resolvable_cost(plan)
    lines = list(plan.lines.select_related('ingredient').all())
    line_details = [build_line_detail(line) for line in lines]
    servings_expected = plan_expected_servings(plan)

    if use_snapshot and plan.snapshot_total_cost is not None:
        per_meal_op = _quantize(
            Decimal(plan.snapshot_other_cost or 0) / Decimal(servings_expected)
        )
        totals = {
            'product_cost': plan.snapshot_product_cost,
            'other_cost': plan.snapshot_other_cost,
            'profit': plan.snapshot_profit,
            'total_cost': plan.snapshot_total_cost,
            'per_meal_rate': plan.snapshot_per_meal_rate,
            'per_meal_operational_cost': per_meal_op,
        }
    else:
        per_meal_op = resolve_per_meal_operational_cost(plan.cycle.year, plan.cycle.month)
        product_cost = sum(
            (Decimal(item['line_product_cost']) for item in line_details),
            Decimal('0.00'),
        )
        totals = calculate_package_totals(
            product_cost=product_cost,
            per_meal_operational_cost=per_meal_op,
            profit_percent=plan.profit_percent,
            expected_servings_count=servings_expected,
        )

    main_servings = sum(
        line.servings_count
        for line in lines
        if line.product_role == MAIN_ROLE
    )

    published_price = plan.meal_category.total_price
    sync_status, sync_delta = _published_price_sync_status(
        totals['total_cost'],
        published_price,
    )
    realized_margin = None
    if sync_status == 'stale' and published_price is not None:
        realized_margin = _realized_profit_margin_percent(
            published_price=Decimal(published_price),
            product_cost=Decimal(totals['product_cost']),
            other_cost=Decimal(totals['other_cost']),
        )

    return {
        'plan_id': plan.id,
        'status': plan.status,
        'cycle': {
            'id': plan.cycle_id,
            'year': plan.cycle.year,
            'month': plan.cycle.month,
            'cycle_days': plan.cycle.cycle_days,
            'total_meals': plan.cycle.total_meals,
        },
        'meal_category': {
            'id': plan.meal_category_id,
            'meal_name': plan.meal_category.meal_name,
            'meal_type': plan.meal_category.meal_type,
            'meal_period': plan.meal_category.meal_period,
            'total_price': (
                str(plan.meal_category.total_price)
                if plan.meal_category.total_price is not None
                else None
            ),
            'pricing_status': plan.meal_category.pricing_status,
        },
        'profit_percent': str(plan.profit_percent),
        'per_meal_operational_cost': str(totals['per_meal_operational_cost']),
        'main_servings_total': main_servings,
        'main_servings_expected': servings_expected,
        'expected_servings': servings_expected,
        'lines': line_details,
        'product_cost': str(totals['product_cost']),
        'other_cost': str(totals['other_cost']),
        'profit': str(totals['profit']),
        'total_cost': str(totals['total_cost']),
        'per_meal_rate': str(totals['per_meal_rate']),
        'suggested_package_price': str(totals['total_cost']),
        'published_meal_total_price': (
            str(published_price) if published_price is not None else None
        ),
        'published_price_status': sync_status,
        'published_price_delta': sync_delta,
        'realized_profit_margin_percent': realized_margin,
        'finalized_at': plan.finalized_at.isoformat().replace('+00:00', 'Z') if plan.finalized_at else None,
        'using_snapshot': bool(use_snapshot and plan.snapshot_total_cost is not None),
    }


def validate_main_servings_for_finalize(plan: MealCyclePlan) -> int:
    main_servings = sum(
        line.servings_count
        for line in plan.lines.all()
        if line.product_role == MAIN_ROLE
    )
    expected = plan_expected_servings(plan)
    if main_servings != expected:
        raise ValidationError(
            {
                'main_servings_total': (
                    f'Main product servings must equal expected servings ({expected}). '
                    f'Current total is {main_servings}.'
                )
            }
        )
    return main_servings


@transaction.atomic
def finalize_plan(plan: MealCyclePlan) -> MealCyclePlan:
    plan = MealCyclePlan.objects.select_for_update().select_related('cycle', 'meal_category').get(pk=plan.pk)
    if plan.is_finalized:
        raise ValidationError({'status': 'Plan is already finalized.'})

    validate_main_servings_for_finalize(plan)
    summary = build_plan_summary(plan, use_snapshot=False)

    plan.status = MealCyclePlan.Status.FINALIZED
    plan.snapshot_product_cost = Decimal(summary['product_cost'])
    plan.snapshot_other_cost = Decimal(summary['other_cost'])
    plan.snapshot_profit = Decimal(summary['profit'])
    plan.snapshot_total_cost = Decimal(summary['total_cost'])
    plan.snapshot_per_meal_rate = Decimal(summary['per_meal_rate'])
    plan.finalized_at = timezone.now()
    plan.save(
        update_fields=[
            'status',
            'snapshot_product_cost',
            'snapshot_other_cost',
            'snapshot_profit',
            'snapshot_total_cost',
            'snapshot_per_meal_rate',
            'finalized_at',
            'updated_at',
        ]
    )
    publish_meal_price_from_plan(plan)
    plan.meal_category.refresh_from_db()
    return plan


@transaction.atomic
def reopen_plan(plan: MealCyclePlan) -> MealCyclePlan:
    from meals.models import MonthlyMenuSchedule

    plan = MealCyclePlan.objects.select_for_update().get(pk=plan.pk)
    if not plan.is_finalized:
        raise ValidationError({'status': 'Only finalized plans can be reopened.'})

    schedule = MonthlyMenuSchedule.objects.filter(plan_id=plan.pk).first()
    if schedule is not None:
        if schedule.is_published:
            raise ValidationError(
                {
                    'menu_schedule': (
                        'Cannot reopen plan while its monthly menu schedule is published. '
                        'Unpublish or delete the schedule first.'
                    )
                }
            )
        # Draft schedule would become quota-orphan after line edits — delete it.
        schedule.delete()

    plan.status = MealCyclePlan.Status.DRAFT
    plan.snapshot_product_cost = None
    plan.snapshot_other_cost = None
    plan.snapshot_profit = None
    plan.snapshot_total_cost = None
    plan.snapshot_per_meal_rate = None
    plan.finalized_at = None
    plan.save(
        update_fields=[
            'status',
            'snapshot_product_cost',
            'snapshot_other_cost',
            'snapshot_profit',
            'snapshot_total_cost',
            'snapshot_per_meal_rate',
            'finalized_at',
            'updated_at',
        ]
    )
    return plan


@transaction.atomic
def replace_plan_lines(plan: MealCyclePlan, line_payloads: list[dict]) -> list[MealCyclePlanLine]:
    if plan.is_finalized:
        raise ValidationError({'status': 'Finalized plans cannot be edited. Reopen the plan first.'})

    ingredient_ids = [item['ingredient'].pk if hasattr(item['ingredient'], 'pk') else item['ingredient'] for item in line_payloads]
    if len(ingredient_ids) != len(set(ingredient_ids)):
        raise ValidationError({'lines': 'Duplicate ingredients are not allowed in one plan.'})

    plan.lines.all().delete()
    created = []
    for item in line_payloads:
        ingredient = item['ingredient']
        if not getattr(ingredient, 'is_active', True):
            raise ValidationError({'ingredient': f'Ingredient "{ingredient}" must be active.'})
        require_resolvable_ingredient_cost(ingredient)
        created.append(
            MealCyclePlanLine.objects.create(
                plan=plan,
                ingredient=ingredient,
                product_role=item['product_role'],
                servings_count=item['servings_count'],
            )
        )
    return created
