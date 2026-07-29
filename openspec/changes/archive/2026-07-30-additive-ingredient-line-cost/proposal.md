## Why

Meal-cycle product costing currently treats kilogram-derived cost and flat `cost_per_customer` as **alternatives** (kg wins, otherwise flat). Operations need both to apply together: kg material cost plus optional per-serving cooking cost. Without additive math, package `product_cost` understates real cost whenever an ingredient has both pricing sources.

## What Changes

- **BREAKING:** Change line product-cost formula from a single effective unit cost × servings to:
  - `line_product_cost = (resolved_cost_per_customer + cost_per_customer) × servings_count`
  - Missing side treated as `0` in the sum (not as “skip this ingredient”).
- **BREAKING:** Redefine `resolved_cost_per_customer` as **kg-only** derived cost (`price_per_kg / customers_per_kg`), or `null` when the ingredient has no complete kg pair — it MUST NOT fall back to flat `cost_per_customer`.
- Keep `product_cost = sum(line_product_cost)` and downstream rollups (`other_cost`, `profit`, `total_cost`, `per_meal_rate`, finalize snapshots) unchanged in structure; only the line inputs change.
- Keep “at least one pricing source” for plan attach / summary / finalize (kg pair and/or flat `cost_per_customer`); still reject fully unpriced ingredients.
- Update calculation services, summary/line detail payloads, tests, backend docs, and frontend docs so clients display and preview the additive formula correctly.
- No new money columns; reuse existing ingredient fields.

## Capabilities

### New Capabilities

<!-- None — this revises existing costing math. -->

### Modified Capabilities

- `meal-cycle-costing`: Line cost MUST use `(resolved_kg_unit + flat_cost_per_customer) × servings_count`; package `product_cost` remains the sum of line costs; clarify null-as-zero only inside that sum when the other source is present.
- `ingredient-catalog`: `resolved_cost_per_customer` is kg-derived only; flat `cost_per_customer` may coexist with kg pricing and MUST be included in costing math (not ignored when kg is present).

## Impact

- **Services:** `meals/services/cycle_calculations.py` — `resolve_cost_per_customer`, `calculate_line_product_cost`, `build_line_detail`, summary/finalize paths.
- **API:** Ingredient read field `resolved_cost_per_customer` semantics change; plan summary line details may expose both unit components plus `line_product_cost`.
- **Tests:** `meals/tests/test_cycle_calculations.py`, `meals/tests/test_meal_cycle_api.py` — especially cases with both kg + flat, and flat-only / kg-only.
- **Docs:** `meals/docs/backend/meal-cycle-management.md`, `meals/docs/frontend/ingredient-per-serving-cost.md`, `FRONTEND_IMPLEMENTATION.md`, plus a dedicated frontend doc for this formula change.
- **Clients:** Admin cycle UI must stop treating resolved vs flat as mutually exclusive; preview math and ingredient forms should show additive unit cost.
- **Finalized plans:** Existing snapshots stay frozen until reopen + recalculate; new summaries after reopen use the additive formula.
