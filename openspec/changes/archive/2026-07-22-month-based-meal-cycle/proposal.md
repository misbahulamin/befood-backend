## Why

Admin meal costing today lives in a messy Excel sheet (`menu analaytic chart.xlsx`) and a partial `Ingredient` / `MealRecipe` API that models the wrong input (`quantity_in_cycle` kg instead of “how many times this food is served”). BeFood needs a month-aware meal cycle planner: days in the month × 2 meals, admin assigns serve counts per product per meal package, then a finalize step shows clear cost and per-meal rate details—plus documentation a non-expert can follow.

## What Changes

- Introduce a **month-based meal cycle** resource (year + month → `cycle_days`, `total_meals = cycle_days × 2`).
- Evolve the product catalog so items support Excel-style pricing: kg-based (`price_per_kg` / `customers_per_kg`) **or** flat `cost_per_customer` (e.g. Vegetables, Dhal, Moshla).
- Replace recipe planning around **serve counts** (times a product appears in the cycle) instead of kg quantity as the primary admin input.
- Add **line cost** and **package summary** calculations matching Excel:
  - `cost_per_customer × servings`
  - product cost total, other cost %, profit %, total cost, per-meal rate
- Add an admin **finalize** workflow that locks (or snapshots) a cycle plan for a meal package and returns the full meal details summary.
- **BREAKING** (admin-only APIs): change `MealRecipe` contract from `quantity_in_cycle` / fixed `cycle_days` toward cycle + servings model (migrate or deprecate existing recipe endpoints).
- Deliver a clear end-to-end markdown guide under `meals/docs/backend/` covering models, formulas, every endpoint, and the admin workflow order.

## Capabilities

### New Capabilities

- `meal-cycle-planning`: Month-scoped cycles, serve-count planning per meal package × product, validation that protein/main slots can fill `total_meals`, finalize + cost summary.
- `meal-cycle-costing`: Cost-per-customer derivation, overhead/profit margins, package totals and per-meal rate using calendar meal count.
- `ingredient-catalog`: Product master list with kg-based and flat-cost items, pieces metadata, active flag (refined from current Ingredient).

### Modified Capabilities

- (none — no existing OpenSpec main specs for meals)

## Impact

- **Code:** `meals/models.py`, recipe serializers/views/filters, `meals/services/recipe_calculations.py`, reuse/extend `meals/services/pricing.py` (`monthrange` × 2 already exists), admin, migrations, tests.
- **APIs:** Admin-only under `/meals/` (cycles, catalog, plan lines, finalize/summary). Public meal list/detail unchanged unless optionally syncing computed rates later (out of scope unless chosen).
- **Docs:** Replace/supersede `docs/meal-ingredients-recipes-api.md` with structured `meals/docs/backend/meal-cycle-management.md`.
- **Data:** Existing `Ingredient` / `MealRecipe` rows need migration strategy (map kg recipes → servings where possible, or clear admin-only seed data).
- **Clients:** Admin frontend recipe builder must switch to month cycle + servings matrix UX (Excel columns A–F become meal packages × products).
