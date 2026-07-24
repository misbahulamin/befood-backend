## 1. Model and migrations

- [x] 1.1 Add `MealCategory.MealPeriod` choices and required `meal_period` field (default `both` for migration safety)
- [x] 1.2 Create migration: add nullable `meal_period`, backfill existing rows to `both`, then set non-null
- [x] 1.3 Add `Order.meal_period_snapshot` with migration: backfill from package when possible, else `lunch` for daily / `both` for multi-day, then require on new orders
- [x] 1.4 Expose `meal_period` on Django admin for `MealCategory`

## 2. Shared serving-count helpers

- [x] 2.1 Implement `periods_per_day(meal_period)` and `expected_servings(meal_type, meal_period, year, month)` (reuse duration day counts aligned with `calculate_order_period`)
- [x] 2.2 Update `calculate_per_meal_price` to divide by package expected servings (not hardcoded `days × 2`)
- [x] 2.3 Unit-test helper cases: daily lunch=1, daily both=2, monthly dinner=days, monthly both=days×2, leap February

## 3. Meal package API

- [x] 3.1 Require and return `meal_period` on meal create/update serializers; include on list/detail/offering payloads
- [x] 3.2 Update OpenAPI schemas/examples for meal endpoints
- [x] 3.3 Tests: create/update validation (required + invalid enum) and response field presence

## 4. Plan editor and costing

- [x] 4.1 Change plan summary to expose `expected_servings` / `main_servings_expected` from package + cycle month
- [x] 4.2 Change finalize main-servings validation to use package expected servings (keep cycle `total_meals` as calendar capacity only)
- [x] 4.3 Change `per_meal_rate` divisor in `cycle_calculations` to expected servings
- [x] 4.4 Tests: finalize success/fail for monthly both (60/62), monthly dinner (30/31), daily both (2); per-meal rate divisors

## 5. Order delivery alignment

- [x] 5.1 Snapshot `meal_period` on order create from the package
- [x] 5.2 Update `_slot_specs_for_order` / `expected_delivery_count` to respect `meal_period_snapshot` (lunch/dinner/both × service days)
- [x] 5.3 Tests: daily lunch=1, daily both=2, monthly dinner=days, monthly both=days×2, weekly lunch=7 / both=14

## 6. Documentation

- [x] 6.1 Backend docs: meal period field, expected-servings formula, plan finalize target, migration defaults
- [x] 6.2 Frontend docs: create-meal `meal_period` UI, plan editor expected servings display, breaking API notes

## 7. Verification

- [x] 7.1 Run focused meals + orders test suites for period/count/pricing/delivery regressions
- [x] 7.2 Smoke-check admin create meal → attach to cycle plan → summary expected servings → finalize
