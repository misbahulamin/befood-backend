## 1. Domain models & migration

- [x] 1.1 Extend `Ingredient` with nullable kg fields, optional flat `cost_per_customer`, `product_role`, and validation that at least one pricing mode is complete
- [x] 1.2 Add `MealCycle` model (`year`, `month`, stored `cycle_days`, `total_meals`, unique year+month)
- [x] 1.3 Add `MealCyclePlan` (`cycle`, `meal_category`, margins, `status`, snapshot cost fields) and `MealCyclePlanLine` (`plan`, `ingredient`, `servings_count`)
- [x] 1.4 Create migrations; decide and apply WIP `MealRecipe` deprecation (remove model/endpoints or leave unused table temporarily)
- [x] 1.5 Register new models in Django admin with useful list filters

## 2. Costing & month services

- [x] 2.1 Extend `meals/services/pricing.py` with `get_month_days(year, month)` and `total_meals_for_month`
- [x] 2.2 Implement `cost_per_customer` derivation and line/package rollup helpers in a dedicated service (Decimal, quantized money)
- [x] 2.3 Implement finalize validation (main servings sum == `total_meals`) and snapshot write helpers
- [x] 2.4 Unit-test formulas against Excel-style examples (Apr 60 meals, Jan 62 meals, 30% other, 10%/20% profit)

## 3. Admin APIs

- [x] 3.1 Update ingredient serializers/views for new fields and pricing validation; keep `IsVerifiedAdmin`
- [x] 3.2 Implement Cycle CRUD (`/meals/cycles/`) with auto-derived days/meals
- [x] 3.3 Implement CyclePlan CRUD + margin patch (`/meals/cycle-plans/`)
- [x] 3.4 Implement plan lines CRUD and bulk replace (`PUT .../lines`) in a transaction
- [x] 3.5 Implement `GET .../summary`, `POST .../finalize`, `POST .../reopen` with correct status codes and problem/validation errors matching project conventions
- [x] 3.6 Wire URLs, filters, OpenAPI/Swagger tags; remove or deprecate `/meals/recipes/`
- [x] 3.7 Confirm public `/meals/` list/detail responses stay free of costing/cycle data

## 4. Tests

- [x] 4.1 API tests: ingredient kg vs flat pricing, authz denial for customer/public
- [x] 4.2 API tests: January/April cycle sizes, unique year-month conflict
- [x] 4.3 API tests: servings matrix, duplicate ingredient rejection, draft summary
- [x] 4.4 API tests: finalize success, main-sum mismatch failure, finalized edit blocked, reopen works
- [x] 4.5 API tests: finalized snapshots ignore later ingredient price changes until reopen

## 5. Documentation

- [x] 5.1 Write `meals/docs/backend/meal-cycle-management.md` with mental model, month→meals rule, all formulas, field meanings, permissions, full workflow order, every endpoint request/response, errors, and checklist
- [x] 5.2 Add a short pointer from `docs/meal-ingredients-recipes-api.md` (or replace) so readers land on the new guide
- [x] 5.3 Include a worked numeric example mapped from the Excel sheet (one meal type, one month)

## 6. Verification

- [x] 6.1 Run targeted meals tests and fix failures
- [x] 6.2 Smoke-check Swagger for new admin endpoints
- [x] 6.3 Mark change ready for review / `/opsx:apply` completion
