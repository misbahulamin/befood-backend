## 1. Backend — meal demand service enrichment

- [x] 1.1 Extend ingredient aggregation in `orders/services/meal_demand.py` to track per-package headcount contributions while aggregating ingredients
- [x] 1.2 Add `customer_count` and `package_contributions` to ingredient quantity dataclasses / `ingredient_qty_to_dict` without changing kg scaling rules
- [x] 1.3 Extend `build_kitchen_requirement` to accept optional `package_public_id`, include `packages[]` from demand, and pass filter into `get_demand`
- [x] 1.4 Confirm snapshot freeze (`_freeze_ingredients`) remains backward compatible (contributions optional / omitted from history JSON in v1)

## 2. Backend — kitchen API contract

- [x] 2.1 Update `IngredientRequirementSerializer` and `KitchenTodayRequirementSerializer` with packages, `customer_count`, and `package_contributions`
- [x] 2.2 Update `KitchenTodayMealRequirementView` to accept `package_public_id`, validate like meal-statistics, and pass it to `build_kitchen_requirement`
- [x] 2.3 Update OpenAPI/`extend_schema` examples and parameters for the kitchen today-requirement endpoint (shared + web URL mounts)
- [x] 2.4 Ensure invalid `service_date` / `meal_period` / `package_public_id` still return `400` with safe messages; customers remain denied

## 3. Backend — tests

- [x] 3.1 Test: kitchen response includes package-wise rows matching `get_demand` finals for a multi-package slot
- [x] 3.2 Test: shared ingredients expose summed `customer_count` and correct `package_contributions` (Student+Regular Dal/Rice style fixture)
- [x] 3.3 Test: single-package items (Vegetable / Fish) show one contribution only
- [x] 3.4 Test: `package_public_id` filter scopes both `packages` and ingredient aggregation
- [x] 3.5 Test: kg quantity still scales by total contributing headcount; flat-cost items keep `quantity_available=false` with headcount present
- [x] 3.6 Test: default slot resolution unchanged when filters omitted; auth denied for non-admin

## 4. Backend — documentation

- [x] 4.1 Update `orders/docs/backend/meal-demand-kitchen-planning.md` (or add kitchen-order-summary section) for packages + contributions + filters
- [x] 4.2 Update `orders/docs/frontend/meal-demand-kitchen-planning.md` with response examples for Kitchen Today dashboard and print consumers

## 5. Frontend — API and types (`befood-frontend`)

- [x] 5.1 Extend meal-demand/kitchen TypeScript types for `packages`, `customer_count`, and `package_contributions`
- [x] 5.2 Update `getKitchenTodayMealRequirement` (and hook) to pass `service_date`, `meal_period`, and optional `package_public_id`
- [x] 5.3 Load package filter options from existing admin meal/package list API already used by Meal Demand (reuse, do not invent a new catalog)

## 6. Frontend — Kitchen Today dashboard UI

- [x] 6.1 Enhance filter bar on `AdminKitchenTodayPage`: date, meal period, package (optional), Apply / Reset / Refresh
- [x] 6.2 Add package-wise summary section (per-package customers + final meals; show expected/meal-off on dashboard)
- [x] 6.3 Enhance item-wise section to show consolidated `customer_count`, package contribution breakdown, and kg when available
- [x] 6.4 Keep overall hero totals + confirmation badge; show incomplete-menu warning when `ingredients_incomplete`
- [x] 6.5 Loading, empty, and error states consistent with existing admin patterns

## 7. Frontend — printable sheet

- [x] 7.1 Add print stylesheet / print layout component with Section 1 packages, Section 2 items, Section 3 prep notes
- [x] 7.2 Wire Print action to current filtered summary state (no unfiltered refetch)
- [x] 7.3 Add Download PDF (client-side from the same layout, or Print-to-PDF UX if no PDF lib is justified) targeting one A4 page for typical data
- [x] 7.4 Verify filtered package mode and incomplete-menu note appear correctly on the sheet

## 8. Frontend QA and polish

- [ ] 8.1 Manual QA: multi-package lunch/dinner slot matches backend counts on screen and print
- [ ] 8.2 Manual QA: package filter + date override + reset default slot
- [ ] 8.3 Manual QA: print/PDF readability for kitchen staff (no truncated totals)
- [ ] 8.4 Smoke-check Meal Demand page still works (unchanged analytics path)

## 9. Post-implementation

- [x] 9.1 Summarize changed files, API delta, and test results for stakeholders
- [x] 9.2 Note follow-ups if any: server PDF, `meal_type` filter, snapshot contribution persistence
