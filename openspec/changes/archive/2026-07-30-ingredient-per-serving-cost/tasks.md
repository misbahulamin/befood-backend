## 1. Catalog validation

- [x] 1.1 Relax `Ingredient.clean` so missing kg pair + missing `cost_per_customer` is allowed; keep kg-pair completeness and positive-value checks
- [x] 1.2 Relax `IngredientSerializer.validate` the same way; ensure `resolved_cost_per_customer` returns null when cost cannot be resolved
- [x] 1.3 Update `Ingredient` / admin help text so `cost_per_customer` is described as optional per-serving cooking cost (one customer or one piece)

## 2. Plan-line and costing guards

- [x] 2.1 Validate resolvable ingredient cost on plan-line create/replace (identify ingredient; never treat missing as zero)
- [x] 2.2 Ensure summary and finalize paths surface clear validation errors when any line ingredient has no resolvable cost

## 3. Tests

- [x] 3.1 Add/update ingredient API tests: create without pricing; create with optional flat `cost_per_customer`; reject incomplete kg pair; `resolved_cost_per_customer` null when unpriced
- [x] 3.2 Add plan-line tests: reject unpriced ingredient; accept kg-priced or flat-priced ingredient
- [x] 3.3 Add/adjust costing tests for summary/finalize rejection when a line ingredient is unpriced
- [x] 3.4 Run the focused meals cycle/ingredient test modules and fix regressions

## 4. Documentation

- [x] 4.1 Update backend meal-cycle / ingredient docs for optional catalog pricing and plan-line cost requirement
- [x] 4.2 Update frontend docs: optional cost field on ingredient form; handle plan-line validation when cost is missing
- [x] 4.3 Refresh OpenAPI/schema notes or examples if serializers change behavior for null resolved cost
