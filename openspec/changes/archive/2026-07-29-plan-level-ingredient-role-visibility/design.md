## Context

Today `Ingredient.product_role` is a global catalog field (`main` / `side` / `staple` / `seasoning` / `other`). Finalize, monthly menu schedule validation/publish, menu sync, and customer/public menu payloads all read role from the ingredient row. That breaks real operations: the same Vegetable may be main for Meal Package A and side for Meal Package D in the same month.

Separately, some catalog rows (e.g. “Masala Cost”) exist only for costing. They must stay on plan lines and in cost rollups, but must not appear on customer-published menus. `is_active` already exists; there is no customer-visibility flag.

Stakeholders: meal ops admins (catalog + cycle plan + schedule), customers (today-menu / package menu), kitchen (admin full schedule).

## Goals / Non-Goals

**Goals:**

- Make `product_role` a property of `MealCyclePlanLine` (package × month × ingredient).
- Keep the same role enum and existing main-fill / one-main-per-slot rules, sourced from plan lines.
- Add `is_customer_visible` on `Ingredient`; customer-facing menu payloads omit non-visible ingredients.
- Costing and admin schedule tooling continue to include all plan ingredients regardless of visibility.
- Migrate existing data safely; update APIs, docs, and tests in one change.

**Non-Goals:**

- Per-slot role overrides (role is fixed for the plan line for that month).
- Renaming `MealCategory` / introducing a new “Meal Package” model.
- Changing costing formulas, margin defaults, or schedule quota math.
- Customer-facing price/cost exposure.
- Multi-tenant or per-branch ingredient catalogs.
- Soft-deleting inactive ingredients from historical schedules (PROTECT remains).

## Decisions

### 1. Store role on `MealCyclePlanLine`, not on schedule slot items

- **Choice**: Add `product_role` to `MealCyclePlanLine` (required). `MonthlyMenuSlotItem` stays ingredient-only; services resolve role via the linked plan’s lines map.
- **Why**: Role is decided when building the monthly package plan (servings matrix), before schedule assignment. Slot items already must belong to the plan quota set; duplicating role on every slot risks drift.
- **Alternatives**: (a) Role on `MonthlyMenuSlotItem` — flexible per day but contradicts “set at plan time” and complicates finalize. (b) Separate join table `(plan, ingredient, role)` — redundant with plan lines. (c) Keep ingredient default + optional plan override — two sources of truth; rejected.

### 2. Move `ProductRole` choices off `Ingredient`

- **Choice**: Relocate `ProductRole` TextChoices to `MealCyclePlanLine` (or a shared meals constants/choices module used by the line). Remove `Ingredient.product_role` after backfill.
- **Why**: Catalog rows become role-agnostic; enum values stay identical for API compatibility of the role *string*.
- **Alternatives**: Keep deprecated nullable field on Ingredient — prolongs dual-read bugs.

### 3. Customer visibility flag naming and defaults

- **Choice**: `Ingredient.is_customer_visible` boolean, default `True`. Follows existing `is_*` naming (`is_active`).
- **Semantics**:
  - `is_active=False` → cannot add to new draft plan lines (existing behavior retained/enforced); still protected on historical rows.
  - `is_customer_visible=False` → still usable on plans and included in cost + admin schedule; filtered out of customer/public menu ingredient lists.
- **Alternatives**: `show_to_customer` — less consistent with codebase. Combining into a single enum — overloads two orthogonal concerns.

### 4. Filter visibility only on customer/public read paths

- **Choice**: Filter in `today_menu`, `package_menu`, and public `meal_offering` menu item serialization. Admin schedule detail, quota summary, sync suggestions, and plan summary keep all ingredients.
- **Why**: Kitchen and costing need full matrices; customers only need Beef/Chicken/Vegetable/Rice-style items.
- **Product_role on customer payloads**: Still returned for visible items, resolved from the package’s plan line for that cycle.

### 5. API contract for plan lines

- **Choice**: Bulk `PUT .../cycle-plans/{id}/lines/` and line serializers require `product_role` per line alongside `ingredient` + `servings_count`. Line read responses expose `product_role` from the line field (not ingredient).
- **Ingredient API**: Remove `product_role` from writable/readable fields; add `is_customer_visible`; keep `is_active`. Filter/order by `product_role` on ingredients removed; add filter on `is_customer_visible`.

### 6. Role resolution helper

- **Choice**: Central helper e.g. `plan_ingredient_role_map(plan) -> dict[ingredient_id, product_role]` used by `cycle_calculations`, `menu_schedule`, `menu_sync`, and customer serializers.
- **Why**: One source of truth; avoids N+1 and inconsistent lookups.

### 7. Keep seasoning / other roles

- **Choice**: Retain full enum (`main`, `side`, `staple`, `seasoning`, `other`) on plan lines even though ops language emphasizes Main/Side/Staple.
- **Why**: Costing-only items and current data already use `seasoning`/`other`; narrowing would force a separate migration of meanings. Customer visibility handles “don’t show Masala Cost,” not role narrowing.

### 8. Breaking change strategy (no dual-write period)

- **Choice**: Single deploy: migrate DB, update all consumers, ship API break for ingredient `product_role` in the same release.
- **Why**: Small admin client surface; dual-read period invites bugs where schedule uses ingredient role while finalize uses line role.
- **Client note**: Document in meals frontend/backend docs; admin must send role on plan line upserts.

## Risks / Trade-offs

- [Existing plans without careful role backfill] → Mitigation: data migration copies `Ingredient.product_role` onto every existing `MealCyclePlanLine` before dropping the column.
- [Admin forgets to set role on new lines] → Mitigation: serializer requires `product_role`; API returns 400/422 on omit/invalid.
- [Same ingredient appears with different roles across packages — customer sees different roles] → Accepted; that is the intended behavior per package plan.
- [Hidden ingredients still occupy schedule slots / quotas] → Accepted for costing fidelity; publish rules for “exactly one main” still count non-visible mains if marked main (ops should not mark Masala Cost as main).
- [Public meal offering `menu_items` currently from plan lines] → Filter by `is_customer_visible`; role from line.
- [Docs mention future `ingredient_type` / serving-matrix XOR] → Out of scope; do not implement; avoid expanding that incomplete path in this change.

## Migration Plan

1. Add `MealCyclePlanLine.product_role` (nullable temporarily) and `Ingredient.is_customer_visible` (default `True`).
2. Data migration: `UPDATE MealCyclePlanLine SET product_role = Ingredient.product_role` via join; set all ingredients `is_customer_visible=True`.
3. Alter `product_role` to non-null with default only if needed for ORM; prefer required without silent default on API writes.
4. Update application code to read/write line role and visibility filters.
5. Remove `Ingredient.product_role` column and ingredient serializer field.
6. Update admin, OpenAPI, docs, tests.
7. Rollback: reverse migration restores column from line values only if a line exists per ingredient (lossy if same ingredient had multiple roles — document as best-effort). Prefer forward-fix over rollback after clients migrate.

## Open Questions

- None blocking: seasoning/other retained; visibility default true; no dual-write. Confirm with ops if any costing ingredients should ship with `is_customer_visible=False` seed data (manual/admin after deploy is enough).
