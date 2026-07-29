from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from meals.models import Ingredient, MealCyclePlan, MealCyclePlanLine
from meals.services.meal_offering import publish_meal_price_from_plan
from meals.services.plan_roles import MAIN_ROLE
from meals.services.pricing import expected_servings


MONEY_PLACES = Decimal('0.01')
COST_PLACES = Decimal('0.000001')


def _quantize(value: Decimal, places: Decimal = MONEY_PLACES) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


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


def resolve_cost_per_customer(ingredient: Ingredient) -> Decimal:
    if ingredient.has_kg_pricing:
        return _quantize(
            Decimal(ingredient.price_per_kg) / Decimal(ingredient.customers_per_kg),
            COST_PLACES,
        )
    if ingredient.cost_per_customer is None:
        raise ValidationError(
            {
                'ingredient': (
                    f'Ingredient "{ingredient.name}" has no usable cost_per_customer.'
                )
            }
        )
    return Decimal(ingredient.cost_per_customer)


def calculate_line_product_cost(cost_per_customer: Decimal, servings_count: int) -> Decimal:
    return _quantize(Decimal(cost_per_customer) * Decimal(servings_count), MONEY_PLACES)


def calculate_estimated_kg(servings_count: int, customers_per_kg: Decimal | None) -> Decimal | None:
    if customers_per_kg is None or customers_per_kg <= 0:
        return None
    return _quantize(Decimal(servings_count) / Decimal(customers_per_kg), Decimal('0.01'))


def build_line_detail(line: MealCyclePlanLine) -> dict:
    ingredient = line.ingredient
    cost_per_customer = resolve_cost_per_customer(ingredient)
    line_product_cost = calculate_line_product_cost(cost_per_customer, line.servings_count)
    estimated_kg = calculate_estimated_kg(line.servings_count, ingredient.customers_per_kg)
    return {
        'id': line.id,
        'ingredient_id': ingredient.id,
        'ingredient_name': ingredient.name,
        'product_role': line.product_role,
        'servings_count': line.servings_count,
        'cost_per_customer': str(_quantize(cost_per_customer, COST_PLACES)),
        'line_product_cost': str(line_product_cost),
        'estimated_kg': str(estimated_kg) if estimated_kg is not None else None,
        'price_per_kg': str(ingredient.price_per_kg) if ingredient.price_per_kg is not None else None,
        'customers_per_kg': (
            str(ingredient.customers_per_kg) if ingredient.customers_per_kg is not None else None
        ),
    }


def calculate_package_totals(
    product_cost: Decimal,
    other_cost_percent: Decimal,
    profit_percent: Decimal,
    expected_servings_count: int,
) -> dict[str, Decimal]:
    if expected_servings_count <= 0:
        raise ValidationError('expected_servings must be greater than 0.')
    other_cost = _quantize(product_cost * (Decimal(other_cost_percent) / Decimal('100')))
    profit = _quantize(product_cost * (Decimal(profit_percent) / Decimal('100')))
    total_cost = _quantize(product_cost + other_cost + profit)
    per_meal_rate = _quantize(total_cost / Decimal(expected_servings_count))
    return {
        'product_cost': _quantize(product_cost),
        'other_cost': other_cost,
        'profit': profit,
        'total_cost': total_cost,
        'per_meal_rate': per_meal_rate,
    }


def build_plan_summary(plan: MealCyclePlan, *, use_snapshot: bool | None = None) -> dict:
    use_snapshot = plan.is_finalized if use_snapshot is None else use_snapshot
    assert_plan_ingredients_have_resolvable_cost(plan)
    lines = list(plan.lines.select_related('ingredient').all())
    line_details = [build_line_detail(line) for line in lines]
    servings_expected = plan_expected_servings(plan)

    if use_snapshot and plan.snapshot_total_cost is not None:
        totals = {
            'product_cost': plan.snapshot_product_cost,
            'other_cost': plan.snapshot_other_cost,
            'profit': plan.snapshot_profit,
            'total_cost': plan.snapshot_total_cost,
            'per_meal_rate': plan.snapshot_per_meal_rate,
        }
    else:
        product_cost = sum(
            (Decimal(item['line_product_cost']) for item in line_details),
            Decimal('0.00'),
        )
        totals = calculate_package_totals(
            product_cost=product_cost,
            other_cost_percent=plan.other_cost_percent,
            profit_percent=plan.profit_percent,
            expected_servings_count=servings_expected,
        )

    main_servings = sum(
        line.servings_count
        for line in lines
        if line.product_role == MAIN_ROLE
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
        'other_cost_percent': str(plan.other_cost_percent),
        'profit_percent': str(plan.profit_percent),
        'main_servings_total': main_servings,
        'main_servings_expected': servings_expected,
        'expected_servings': servings_expected,
        'lines': line_details,
        'product_cost': str(totals['product_cost']),
        'other_cost': str(totals['other_cost']),
        'profit': str(totals['profit']),
        'total_cost': str(totals['total_cost']),
        'per_meal_rate': str(totals['per_meal_rate']),
        'suggested_package_price': str(
            _quantize(totals['per_meal_rate'] * Decimal(servings_expected))
        ),
        'published_meal_total_price': (
            str(plan.meal_category.total_price)
            if plan.meal_category.total_price is not None
            else None
        ),
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
