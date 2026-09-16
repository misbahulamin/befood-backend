## 1. Shared pricing service

- [x] 1.1 Add `meals/services/pricing.py` with `calculate_meal_price(ingredient_cost, operational_cost, profit_percent)` using existing money quantization rules
- [x] 1.2 Refactor `build_one_meal_price_preview` to use `calculate_meal_price` for profit/final price arithmetic
- [x] 1.3 Refactor Instant snapshot and live pricing branches in `instant_meals.py` to use `calculate_meal_price` without changing Instant card field names
- [x] 1.4 Add unit tests for subscriber (20% → 130) and Instant (70% → 180) worked examples from the specs

## 2. Admin published menu / schedule dual pricing

- [x] 2.1 Extend `serialize_schedule_assignments` (admin `include_final_price` path) to load Instant settings once and attach cost + `subscriber_pricing` + `instant_pricing` + flat aliases
- [x] 2.2 Prefer publish snapshots for ingredient/operational cost on published slots; leave unpriceable/draft slots null (no fabricated zeros)
- [x] 2.3 Keep `final_meal_price` as subscriber selling price (backward compatible)
- [x] 2.4 Update OpenAPI / serializer docs for the enriched assignment fields

## 3. Safety and Instant settings integration

- [x] 3.1 Verify Instant `profit_percent` comes from `InstantMealSettings.load()` only (no hardcode)
- [x] 3.2 Add regression asserting Instant settings PATCH does not mutate slot subscriber snapshots
- [x] 3.3 Confirm delivery/wallet charge path still uses `final_meal_price_snapshot` only (no code change unless a leak is found)

## 4. API and integration tests

- [x] 4.1 Admin schedule detail test: published slot returns dual ladders matching the 48.15 / 4.13 / 14.45% / 70% worked example
- [x] 4.2 Admin schedule detail test: Instant percent 70 → 80 refreshes Instant price only
- [x] 4.3 Multi-slot test: different ingredient costs produce distinct subscriber and Instant prices
- [x] 4.4 Cost-preview regression: existing cost-preview response still matches shared helper

## 5. Documentation

- [x] 5.1 Update backend docs for monthly menu schedule / slot pricing with dual-pricing contract and formula
- [x] 5.2 Add or update frontend doc for admin published-menus page: render-only fields, table columns, no client-side calculation
- [x] 5.3 Note Instant settings change requires refresh (no republish) for Instant ladder only
