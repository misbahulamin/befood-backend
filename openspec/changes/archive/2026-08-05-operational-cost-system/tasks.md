## 1. Models and migrations

- [x] 1.1 Add `OperationalCostMonth` (`public_id`, `year`, `month`, `target_meal_quantity`, timestamps) with unique `(year, month)`
- [x] 1.2 Add `OperationalCostItem` (`public_id`, FK to month, `name`, `amount`, optional `notes`/`sort_order`, timestamps)
- [x] 1.3 Register models in Django admin; generate and apply migrations
- [x] 1.4 Stop using `MealCyclePlan.other_cost_percent` in serializers/writes; remove field via migration (or leave unused then drop) after callers are updated

## 2. Operational cost services

- [x] 2.1 Implement total and `per_meal_operational_cost` helpers (Decimal, `ROUND_HALF_UP`, money `0.01`)
- [x] 2.2 Implement `resolve_per_meal_operational_cost(year, month)` that errors when month/target missing
- [x] 2.3 Cover service edge cases: empty items → `0.00`, invalid target rejected

## 3. Operational cost admin APIs

- [x] 3.1 Add serializers + ViewSet for operational cost months (list/create/retrieve/update/delete) with `IsVerifiedAdmin`
- [x] 3.2 Support nested or replace-all item management (`PUT .../items/` and/or item CRUD)
- [x] 3.3 Expose computed `total_operational_cost` and `per_meal_operational_cost` on responses
- [x] 3.4 Wire URLs under `/meals/` and OpenAPI examples; permission tests for customer/anon denial

## 4. Cycle costing formula update

- [x] 4.1 Change `calculate_package_totals` to use `other_cost = expected_servings × per_meal_operational_cost` and drop percent-based other cost
- [x] 4.2 Update `build_plan_summary` / `finalize_plan` to resolve monthly op cost; fail with clear validation when missing
- [x] 4.3 Include `per_meal_operational_cost` in admin plan summary/finalize payloads
- [x] 4.4 Update cycle plan serializers to remove `other_cost_percent` write/read as costing input; keep `profit_percent`

## 5. Admin cost preview

- [x] 5.1 Add verified-admin `cost-preview` action on cycle plans (selected ingredient public_ids → unit costs + op cost + profit + final meal price)
- [x] 5.2 Ensure public meal/customer APIs do not expose ledger, per-meal op cost, profit percent, or preview

## 6. Tests

- [x] 6.1 Unit tests: July example `310000 / 10000 = 31`; package other_cost = servings × per-meal op cost
- [x] 6.2 API tests: CRUD months/items; unique year-month; target ≤ 0 rejected
- [x] 6.3 Summary/finalize fail without operational month; succeed with month and snapshot absolute other_cost
- [x] 6.4 Permission tests: only verified admin sees operational cost and cost preview
- [x] 6.5 Regression: existing cycle calculation tests updated for new formula (no `other_cost_percent`)

## 7. Documentation

- [x] 7.1 Update `meals/docs` cycle costing docs with operational ledger, target meals, and new Meal Price formula
- [x] 7.2 Document breaking change: `other_cost_percent` no longer drives other cost; admins must set monthly operational cost before summary/finalize
- [x] 7.3 Note frontend follow-up: Admin UI for ledger + live preview (out of scope for this backend change)
