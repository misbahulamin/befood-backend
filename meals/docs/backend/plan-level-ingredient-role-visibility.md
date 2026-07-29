# Plan-level ingredient role & customer visibility

## Quick summary

| Concern | Where it lives | Notes |
| --- | --- | --- |
| Serving role (`main` / `side` / `staple` / `seasoning` / `other`) | `MealCyclePlanLine.product_role` | Per meal package × month |
| Catalog active flag | `Ingredient.is_active` | Cannot add inactive to new draft lines |
| Customer menu visibility | `Ingredient.is_customer_visible` | Default `true`; costing still includes hidden items |
| Customer/public menus | today-menu, my-package-menu, public `menu_items` | Omit `is_customer_visible=false`; role from plan line |
| Admin schedule / summary / finalize | Full plan lines | Includes hidden ingredients |

**BREAKING:** Ingredient create/update no longer accepts or returns `product_role`. Bulk `PUT /meals/cycle-plans/{id}/lines/` requires `product_role` on each line.

## Admin workflow

1. `POST /meals/ingredients/` — pricing + `is_active` + `is_customer_visible` (no role).
2. Create cycle + plan for a package/month.
3. `PUT .../cycle-plans/{public_id}/lines/` with `{ ingredient, servings_count, product_role }`.
4. Finalize (main plan-line servings must match expected servings).
5. Build/publish monthly menu schedule (main rules use plan-line roles).

Same ingredient may be `main` on Package A and `side` on Package D in the same cycle.

## Example line matrix

```json
{
  "lines": [
    { "ingredient": 1, "servings_count": 60, "product_role": "main" },
    { "ingredient": 5, "servings_count": 60, "product_role": "staple" },
    { "ingredient": 9, "servings_count": 60, "product_role": "seasoning" }
  ]
}
```

## Migration

`meals.0012_plan_level_ingredient_role_visibility` backfills line roles from the old ingredient role, defaults visibility to `true`, then drops catalog `product_role`.

## Related

- Backend cycle docs: [`meal-cycle-management.md`](./meal-cycle-management.md)
- Frontend customer menu: [`../frontend/customer-package-menu.md`](../frontend/customer-package-menu.md)
- Frontend admin note: [`../frontend/plan-level-ingredient-role-visibility.md`](../frontend/plan-level-ingredient-role-visibility.md)
- OpenSpec: `openspec/changes/plan-level-ingredient-role-visibility/`
