from decimal import Decimal

from meals.models import MealCategory, MealCyclePlan
from meals.services.pricing import calculate_per_meal_price


def get_latest_finalized_plan(meal: MealCategory) -> MealCyclePlan | None:
    return (
        MealCyclePlan.objects.filter(
            meal_category=meal,
            status=MealCyclePlan.Status.FINALIZED,
        )
        .select_related('cycle', 'meal_category')
        .prefetch_related('lines__ingredient')
        .order_by('-cycle__year', '-cycle__month', '-finalized_at')
        .first()
    )


def build_public_cycle_offering(plan: MealCyclePlan) -> dict:
    """Customer-safe offering: no supplier kg unit prices."""
    menu_items = [
        {
            'name': line.ingredient.name,
            'product_role': line.ingredient.product_role,
            'servings_count': line.servings_count,
        }
        for line in plan.lines.all()
    ]
    finalized_at = None
    if plan.finalized_at:
        finalized_at = plan.finalized_at.isoformat().replace('+00:00', 'Z')

    return {
        'plan_id': plan.id,
        'year': plan.cycle.year,
        'month': plan.cycle.month,
        'cycle_days': plan.cycle.cycle_days,
        'total_meals': plan.cycle.total_meals,
        'package_total_price': str(plan.snapshot_total_cost) if plan.snapshot_total_cost is not None else None,
        'per_meal_rate': str(plan.snapshot_per_meal_rate) if plan.snapshot_per_meal_rate is not None else None,
        'product_cost': str(plan.snapshot_product_cost) if plan.snapshot_product_cost is not None else None,
        'other_cost': str(plan.snapshot_other_cost) if plan.snapshot_other_cost is not None else None,
        'profit': str(plan.snapshot_profit) if plan.snapshot_profit is not None else None,
        'finalized_at': finalized_at,
        'menu_items': menu_items,
    }


def resolve_public_per_meal_price(meal: MealCategory, offering_plan: MealCyclePlan | None = None) -> str | None:
    plan = offering_plan if offering_plan is not None else get_latest_finalized_plan(meal)
    if plan is not None and plan.snapshot_per_meal_rate is not None:
        return str(plan.snapshot_per_meal_rate)
    if meal.total_price is None:
        return None
    return str(calculate_per_meal_price(meal.total_price))


def publish_meal_price_from_plan(plan: MealCyclePlan) -> MealCategory:
    meal = plan.meal_category
    if plan.snapshot_total_cost is None:
        raise ValueError('Cannot publish meal price without snapshot_total_cost.')
    meal.total_price = plan.snapshot_total_cost
    meal.save(update_fields=['total_price', 'updated_at'])
    return meal
