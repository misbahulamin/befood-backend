from __future__ import annotations

from meals.models import MealCyclePlan, MealCyclePlanLine


def plan_ingredient_role_map(plan: MealCyclePlan) -> dict[int, str]:
    """Map ingredient_id -> product_role for a cycle plan's lines."""
    return {
        line.ingredient_id: line.product_role
        for line in plan.lines.all()
    }


def plan_line_role_for_ingredient(plan: MealCyclePlan, ingredient_id: int) -> str | None:
    return plan_ingredient_role_map(plan).get(ingredient_id)


MAIN_ROLE = MealCyclePlanLine.ProductRole.MAIN
