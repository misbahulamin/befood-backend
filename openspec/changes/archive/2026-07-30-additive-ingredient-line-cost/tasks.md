## 1. Calculation service

- [x] 1.1 Update `meals/services/cycle_calculations.py` so kg resolution never falls back to flat `cost_per_customer`
- [x] 1.2 Implement combined unit cost: `(resolved_kg or 0) + (flat or 0)` and `line_product_cost = combined × servings_count`
- [x] 1.3 Update `build_line_detail` to expose both unit components used in the sum plus `line_product_cost`
- [x] 1.4 Confirm `ingredient_has_resolvable_cost` / plan attach / summary / finalize still require at least one pricing source

## 2. API serializers

- [x] 2.1 Change ingredient `resolved_cost_per_customer` SerializerMethodField to kg-only (`null` when no kg pair)
- [x] 2.2 Update OpenAPI / view descriptions that still say resolved ignores flat or equals exclusive effective cost

## 3. Tests

- [x] 3.1 Update `test_cycle_calculations` for kg-only, flat-only, and additive kg+flat line costs
- [x] 3.2 Update ingredient API tests so flat-only ingredients return `resolved_cost_per_customer = null`
- [x] 3.3 Add/adjust summary/finalize tests asserting `product_cost` is the sum of additive `line_product_cost` values
- [x] 3.4 Run `python manage.py test meals.tests.test_cycle_calculations meals.tests.test_meal_cycle_api`

## 4. Documentation

- [x] 4.1 Update backend money formulas in `meals/docs/backend/meal-cycle-management.md`
- [x] 4.2 Write frontend guide `meals/docs/frontend/additive-ingredient-line-cost.md` (formula, field meanings, UI states, examples)
- [x] 4.3 Update `meals/docs/frontend/ingredient-per-serving-cost.md` to remove “kg ignores flat” wording
- [x] 4.4 Update `meals/docs/frontend/FRONTEND_IMPLEMENTATION.md` pricing field notes for additive costing
- [x] 4.5 Touch `meals/docs/backend/ingredient-per-serving-cost.md` if it still describes exclusive resolve semantics
