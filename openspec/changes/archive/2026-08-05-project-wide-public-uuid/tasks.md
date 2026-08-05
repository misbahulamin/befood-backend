## 1. Convention baseline

- [x] 1.1 Document/shared helper: optional `PublicIdMixin` (or project note) matching `MealCategory.public_id` field shape
- [x] 1.2 Add a short convention note under `meals/docs` or a shared `docs/` pointer linking to this change (field + naming + lookup rules)
- [x] 1.3 Confirm Phase 0 complete (`MealCategory` + `meal_public_id`) and list remaining integer exposures via repo grep (`order_id`, `delivery_id`, address `id`)

## 2. Phase 1 — Order + OrderDelivery

- [x] 2.1 Add `public_id` to `Order` and `OrderDelivery` with safe backfill migrations
- [x] 2.2 Update customer + web order serializers: `id` → `public_id`; nested deliveries use `public_id`
- [x] 2.3 Set `lookup_field = "public_id"` on order ViewSets; update cancel / meal-off / mark-delivery URL identity
- [x] 2.4 Update today-board and today-menu payloads: `order_id` → `order_public_id`; delivery refs by UUID
- [x] 2.5 Update OpenAPI examples and orders tests for UUID paths and payloads
- [x] 2.6 Write `orders/docs/frontend/order-public-uuid.md` (+ backend notes) and cross-link full-order-process / meal-off docs

## 3. Phase 2 — CustomerAddress

- [x] 3.1 Add `public_id` to `CustomerAddress` with safe backfill migration
- [x] 3.2 Update address ViewSet lookup + serializers; update set-default action to accept address `public_id`
- [x] 3.3 Align nested profile address payloads with `public_id`
- [x] 3.4 Update user_management tests and write `user_management/docs/frontend/address-public-uuid.md` (create docs paths if missing)

## 4. Phase 3 — Ops catalog (optional)

- [x] 4.1 Add `public_id` to `Ingredient`, `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine`, `MonthlyMenuSchedule` (backfill migrations)
- [x] 4.2 Switch manager ViewSet lookups and nested admin serializers to UUID (retain integer only if transitional need is documented)
- [x] 4.3 Update meals cycle/schedule tests and frontend ops docs

## 5. Phase 4 — Deferred domains readiness

- [x] 5.1 Audit stub models in `wallet`, `payments`, `delivery`, `promotions`, `notifications` for first public endpoints
- [x] 5.2 For each app, when first client API is implemented: add `public_id`, UUID lookup, no customer integer `id`, plus docs checklist
- [x] 5.3 Add a PR/review checklist item (or cursor rule note) that new public resources MUST ship with `public_id`

## 6. Verification and rollout

- [x] 6.1 Run phase-scoped `makemigrations` / `migrate` and targeted tests after each phase
- [x] 6.2 Grep for leftover customer-facing integer identity fields after Phase 1–2
- [x] 6.3 Coordinate frontend cutover notes per phase (no dual int/UUID support after each cutover)
