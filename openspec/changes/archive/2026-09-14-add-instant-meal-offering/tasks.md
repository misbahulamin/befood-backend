## 1. Settings model and migration



- [x] 1.1 Confirm `InstantMealSettings` in `meals/models.py` matches design (default profit `50.00`, `duration_days` allowlist `{1,3,7,15,25,30}`, singleton `load()` / non-delete)

- [x] 1.2 Add model-level or serializer validation rejecting `duration_days` outside the allowlist

- [x] 1.3 Create and apply Django migration for `InstantMealSettings` only (no changes to menu/slot/plan tables)

- [x] 1.4 Register `InstantMealSettings` in Django admin (read/update singleton; mirror `MenuRevealSettings` pattern)



## 2. Instant Meal pricing and list services



- [x] 2.1 Add `meals/services/instant_meals.py` with helpers: resolve date window from settings + local today; query published slots in range with package/ingredients prefetch

- [x] 2.2 Implement Instant price computation reusing existing cost helpers / `build_one_meal_price_preview` with Instant `profit_percent`; prefer `ingredient_cost_snapshot`; resolve month per-meal operational cost without writing slot snapshots

- [x] 2.3 Build Instant card DTOs (`public_id`, `name`, `meal_period`, `service_date`, package fields, `price`, `ingredient_cost`, optional `image`, `subscriber_price`) and stable sort (date → lunch/dinner → package)

- [x] 2.4 Skip unpriceable slots (missing op-cost / unresolved ingredients) without failing the whole list; do not invent zero operational cost silently



## 3. Admin Instant Meal settings API



- [x] 3.1 Add serializer for Instant Meal settings (`profit_percent`, `duration_days`, `updated_at` read-only)

- [x] 3.2 Add `GET|PATCH` view with `IsVerifiedAdmin` at `/meals/instant-meal-settings/`

- [x] 3.3 Wire URL name and OpenAPI/schema helpers consistent with `menu-reveal-settings`



## 4. Public Instant Meal list API



- [x] 4.1 Add list serializer/view for Instant Meals (AllowAny or same public posture as `public-package-menu`)

- [x] 4.2 Add `GET /meals/instant-meals/` with pagination and documented ordering

- [x] 4.3 Ensure response does not mutate subscription data and does not include marketing copy strings (frontend owns upsell text from `subscriber_price`)



## 5. Tests



- [x] 5.1 Admin settings tests: defaults, patch profit/duration, reject invalid duration, non-admin denied

- [x] 5.2 Instant list tests: published slots only; past dates excluded; duration window; lunch+dinner separate; multi-package cards; ordering

- [x] 5.3 Pricing tests: Instant formula with ingredient + op-cost + Instant profit; changing Instant profit does not alter slot `final_meal_price_snapshot` or plan `profit_percent`

- [x] 5.4 Regression smoke: existing package menu / slot publish pricing tests still pass



## 6. Documentation



- [x] 6.1 Write `meals/docs/backend/instant-meal-offering.md` (formula, isolation rules, endpoints, errors, verification)

- [x] 6.2 Write `meals/docs/frontend/instant-meal-offering.md` (auth, endpoint grid, field meanings, example JSON, settings UI flow, no-order note, upsell from `subscriber_price`)

