## Why

Ingredient `product_role` (main / side / staple / …) is currently global on the catalog row, but the same ingredient must play different roles across meal packages (e.g. Vegetable as main in Package A and side in Package D). Admins also need catalog-level control over whether an ingredient appears on customer-published menus (e.g. “Masala Cost” for costing only) while still counting in cost calculations.

## What Changes

- **BREAKING**: Remove `product_role` from `Ingredient` create/update/list contracts. Role is no longer a catalog property.
- Add required `product_role` on each `MealCyclePlanLine` when admins build a package×month servings matrix, so role is scoped to that meal package and cycle.
- Rewire finalize, schedule assignment, publish, menu sync, and public/customer menu payloads to resolve role from the plan line (not the ingredient).
- Keep existing `is_active` on ingredients; add `is_customer_visible` so admins can hide costing-only items from customer-facing published menus while retaining them in plan costing and admin schedule tools.
- Customer `today-menu`, `my-package-menu`, and public meal `menu_items` MUST omit ingredients with `is_customer_visible=false` (and MUST NOT expose inactive ingredients on customer paths).
- Admin schedule/costing views continue to include all plan ingredients regardless of customer visibility.
- Data migration: copy each ingredient’s current `product_role` onto existing `MealCyclePlanLine` rows, default `is_customer_visible=true`, then drop `Ingredient.product_role`.
- Update OpenAPI, admin filters, backend/frontend docs, and tests accordingly.

## Capabilities

### New Capabilities

- `ingredient-customer-visibility`: Catalog flag controlling whether an ingredient may appear on customer-published menu payloads; independent of costing inclusion and of plan-level role.

### Modified Capabilities

- `ingredient-catalog`: Drop global `product_role`; keep pricing/`is_active`/`notes`; add `is_customer_visible`.
- `meal-cycle-planning`: Plan lines carry `product_role`; finalize main-servings validation uses plan-line roles.
- `customer-meal-package-menu`: Customer menu ingredient lists resolve `product_role` from the package’s plan lines and exclude non-customer-visible ingredients.

## Impact

- **Models**: `meals.Ingredient`, `meals.MealCyclePlanLine`; migration + backfill.
- **Services**: `cycle_calculations`, `menu_schedule`, `menu_sync`, `today_menu`, `package_menu`, `meal_offering`.
- **APIs**: ingredient CRUD serializers/filters; cycle plan line bulk replace + serializers; schedule assignment responses; customer/public menu responses.
- **Admin**: ingredient list filters; plan-line role display/filter.
- **Specs/docs/tests**: ingredient-catalog, meal-cycle-planning, customer menus, monthly schedule tests, meal-cycle API tests.
- **Clients**: admin UI must set role when editing plan lines; stop sending `product_role` on ingredient create; respect `is_customer_visible`.
