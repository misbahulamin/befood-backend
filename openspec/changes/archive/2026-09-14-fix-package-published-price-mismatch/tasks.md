## 1. Summary response fixes

- [x] 1.1 In `build_plan_summary` (`meals/services/cycle_calculations.py`), set `suggested_package_price` to `str(totals['total_cost'])` instead of `per_meal_rate × servings`
- [x] 1.2 Add helper `_published_price_sync_status(total_cost, published_price) -> (status, delta)` in `cycle_calculations.py`
- [x] 1.3 Add `published_price_status` and `published_price_delta` fields to summary response dict
- [x] 1.4 (Optional) Add `realized_profit_margin_percent` when status is `stale` per design.md

## 2. Tests

- [x] 2.1 Add `test_suggested_package_price_equals_total_cost` in `meals/tests/test_cycle_calculations.py` using non-divisible total (e.g. 3161.08 / 60)
- [x] 2.2 Add `test_draft_summary_stale_published_after_op_cost_change`: finalize → update operational cost month → reopen or view draft → assert `published_price_status=stale` and delta `47.42` pattern
- [x] 2.3 Add `test_finalize_summary_published_price_in_sync` in `meals/tests/test_meal_cycle_api.py` asserting new sync fields on finalize response
- [x] 2.4 Add `test_profit_base_is_product_cost_only` documenting intentional 15%-on-product-cost behavior
- [x] 2.5 Run `python manage.py test meals.tests.test_cycle_calculations meals.tests.test_meal_cycle_api`

## 3. Documentation

- [x] 3.1 Fix `meals/docs/backend/meal-cycle-management.md` §9.6: finalize **does** publish `snapshot_total_cost` to `MealCategory.total_price` via `publish_meal_price_from_plan`
- [x] 3.2 Document new `published_price_status` / `published_price_delta` fields and stale-price workflow (re-finalize after op-cost change)
- [x] 3.3 Note in docs that profit margin is on product cost only, not total package cost

## 4. API / OpenAPI (if cycle openapi module exists)

- [x] 4.1 Update cycle plan summary OpenAPI schema with `published_price_status`, `published_price_delta`, corrected `suggested_package_price` description

## 5. Frontend handoff (out of repo)

- [x] 5.1 Package summary UI: when `published_price_status=stale`, show warning and delta; label Published Meal Price as "Last published" on draft plans (`befood-frontend`: `AdminPlanSummaryPanel.tsx`)
- [x] 5.2 Clarify profit margin label: "15% on product cost" vs package margin (`AdminPlanSummaryPanel.tsx`, `AdminCyclePlanEditorPage.tsx`)
