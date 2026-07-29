# Optional ingredient per-serving cost (Backend)

## Quick summary

Ingredient catalog pricing is optional. Flat `cost_per_customer` is optional cooking cost for one customer or one piece. It may coexist with kg pricing. Meal-cycle plan attach / summary / finalize still require at least one resolvable pricing source.

| Concern | Behavior |
| --- | --- |
| Catalog create/update | Kg pair (both), flat `cost_per_customer`, **both**, or neither |
| Incomplete kg pair | `400` |
| `resolved_cost_per_customer` | Kg-only (`price_per_kg / customers_per_kg`); `null` without kg pair (does not fall back to flat) |
| Line costing | `(resolved + flat) × servings_count` — missing side treated as `0` |
| Plan line create / bulk replace | Rejects ingredient with neither kg nor flat (`ingredient` error) |
| Summary / finalize | Rejects plans with any unpriced line ingredient |

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| `POST`/`PATCH` | `/meals/ingredients/` | Pricing fields optional; both sources allowed |
| `POST` | `/meals/cycle-plan-lines/` | Requires resolvable cost |
| `PUT` | `/meals/cycle-plans/{public_id}/lines/` | Same |
| `GET` | `/meals/cycle-plans/{public_id}/summary/` | `400` if any line unpriced |
| `POST` | `/meals/cycle-plans/{public_id}/finalize/` | Same |

## Permissions

Verified admin only (`IsVerifiedAdmin`) — unchanged.

## Verification

```bash
python manage.py test meals.tests.test_meal_cycle_api meals.tests.test_cycle_calculations
```

See also: [`meal-cycle-management.md`](./meal-cycle-management.md), frontend [`../frontend/additive-ingredient-line-cost.md`](../frontend/additive-ingredient-line-cost.md), OpenSpec change `additive-ingredient-line-cost`.
