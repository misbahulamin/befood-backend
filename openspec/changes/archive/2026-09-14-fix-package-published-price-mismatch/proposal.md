## Why

Package summary screens show **Total Cost** and **Published Meal Price** side by side, but they can diverge by tens of taka even when the admin expects a 15% profit margin. On the Student Package (Both, 60 servings) example, Total Cost is ৳3161.08 while Published Meal Price is ৳3113.66 — a ৳47.42 gap that reduces realized margin to ~12% instead of the stated 15%. Investigation shows this is not a rounding error in profit math; it is a **data-source mismatch** between live-calculated totals and a stale published price that only updates on finalize.

## What Changes

- Document and fix the summary contract so **Published Meal Price** is unambiguous: either equals authoritative `total_cost` (when finalized) or is clearly labeled as stale/last-published when draft live totals differ.
- Add summary metadata (`published_price_status`, `published_price_delta`) so admins see when live totals and published price are out of sync and why (e.g. operational cost ledger changed since last finalize).
- Fix `suggested_package_price` to derive from `total_cost` (not `round(per_meal_rate) × servings`) to eliminate secondary rounding drift.
- Add backend tests that reproduce the Student Package scenario and assert consistency rules after finalize and after operational-cost changes on draft plans.
- Update admin docs to clarify profit-base (product cost only, per spec) and the finalize → publish flow (contradicts outdated doc line claiming finalize does not write `MealCategory.total_price`).

## Capabilities

### New Capabilities

_None — this is a bug fix within existing meal-cycle costing and planning._

### Modified Capabilities

- `meal-cycle-planning`: Summary response must expose published-price sync status and prevent misleading side-by-side totals on draft plans without context.
- `meal-cycle-costing`: `suggested_package_price` must equal `total_cost`; add invariant tests for published vs total cost consistency.

## Impact

- **Backend:** `meals/services/cycle_calculations.py` (`build_plan_summary`, `calculate_package_totals`), `meals/services/meal_offering.py` (`publish_meal_price_from_plan`), `meals/api/cycle_views.py` (summary/finalize responses), tests in `meals/tests/test_cycle_calculations.py` and `meals/tests/test_meal_cycle_api.py`.
- **Docs:** `meals/docs/backend/meal-cycle-management.md` (outdated finalize/publish note).
- **Frontend (befood frontend, out of repo):** Package summary screen should consume new sync fields and label Published Meal Price appropriately on draft vs finalized plans.
- **No breaking API removals**; additive response fields only. Existing finalize → `MealCategory.total_price` behavior is preserved and strengthened with tests.
