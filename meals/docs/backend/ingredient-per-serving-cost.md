# Optional ingredient per-serving cost (Backend)

## Quick summary

Ingredient catalog pricing is optional. Flat `cost_per_customer` means optional cooking cost for one customer or one piece. Meal-cycle plan attach / summary / finalize still require a resolvable cost.

| Concern | Behavior |
| --- | --- |
| Catalog create/update | Kg pair (both), flat `cost_per_customer`, or neither |
| Incomplete kg pair | `400` |
| `resolved_cost_per_customer` | Derived cost, or `null` if unpriced |
| Plan line create / bulk replace | Rejects unpriced ingredient (`ingredient` error) |
| Summary / finalize | Rejects plans with any unpriced line ingredient |

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| `POST`/`PATCH` | `/meals/ingredients/` | Pricing fields optional |
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

See also: [`meal-cycle-management.md`](./meal-cycle-management.md), OpenSpec change `ingredient-per-serving-cost`.
