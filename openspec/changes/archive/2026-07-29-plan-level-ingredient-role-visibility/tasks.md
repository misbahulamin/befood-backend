## 1. Data model and migration

- [x] 1.1 Move `ProductRole` choices to `MealCyclePlanLine` (or shared meals choices) and add required `product_role` field on `MealCyclePlanLine`
- [x] 1.2 Add `Ingredient.is_customer_visible` (`BooleanField`, default `True`)
- [x] 1.3 Create migration: add nullable line `product_role` + `is_customer_visible`, backfill line roles from `Ingredient.product_role`, set visibility true, then make line role non-null and remove `Ingredient.product_role`
- [x] 1.4 Update Django admin for ingredient visibility and plan-line `product_role` display/filters

## 2. Role resolution and costing services

- [x] 2.1 Add `plan_ingredient_role_map(plan)` (and related helpers) in meals services
- [x] 2.2 Update `cycle_calculations.build_line_detail`, `build_plan_summary`, and `validate_main_servings_for_finalize` to use plan-line `product_role`
- [x] 2.3 Ensure costing still includes all plan lines regardless of `is_customer_visible`

## 3. Ingredient and cycle-plan APIs

- [x] 3.1 Update `IngredientSerializer` / filters / ordering: remove `product_role`; add `is_customer_visible`
- [x] 3.2 Update plan-line serializers and bulk `PUT .../lines/` to require and persist `product_role` per line
- [x] 3.3 Update OpenAPI/schema metadata for ingredient and cycle-plan line contracts

## 4. Menu schedule and sync

- [x] 4.1 Update `menu_schedule` role lookups, assignment validation, incomplete-main detection, publish, and serialization to use plan-line roles
- [x] 4.2 Update `menu_sync` to use plan-line roles for main targeting and payload fields
- [x] 4.3 Keep admin schedule/quota responses including customer-hidden ingredients

## 5. Customer and public menu visibility

- [x] 5.1 Filter `is_customer_visible=false` in `today_menu` and resolve `product_role` from plan lines
- [x] 5.2 Filter and resolve roles the same way in `package_menu`
- [x] 5.3 Filter public `meal_offering` `menu_items` by visibility; expose plan-line `product_role`

## 6. Tests

- [x] 6.1 Update meal-cycle API/calculation tests for plan-line roles and ingredient create without `product_role`
- [x] 6.2 Add/adjust tests: same ingredient different roles across two packages; finalize uses plan-line mains
- [x] 6.3 Update monthly menu schedule / sync tests for plan-line role validation
- [x] 6.4 Add customer visibility tests for today-menu, package-menu, public offering (hidden omitted; admin schedule still full)
- [x] 6.5 Run targeted meals test suite and fix regressions

## 7. Documentation

- [x] 7.1 Update `meals/docs/backend` meal-cycle / menu-schedule docs for plan-line role + `is_customer_visible`
- [x] 7.2 Update `meals/docs/frontend` customer menu and admin implementation docs (breaking ingredient contract + line payload)
- [x] 7.3 Note migration/backfill behavior for ops in backend docs
