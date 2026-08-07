## 1. Domain service foundation

- [x] 1.1 Add shared meal-demand helpers that resolve meal-off timezone, slot deadline, and `confirmation_status` (`estimated` | `confirmed`) for `(service_date, meal_period)`
- [x] 1.2 Implement `get_demand(service_date, meal_period, package_id=None)` aggregating non-cancelled `OrderDelivery` rows into expected, meal-off (`skipped`), final cooking counts, and package-wise breakdown
- [x] 1.3 Implement `resolve_default_kitchen_slot(now)` → today + lunch if local time `< dinner_off_time`, else dinner
- [x] 1.4 Implement ingredient requirement builder from published monthly menu slot assignments × package final counts using `Decimal` and `kg_per_person = 1 / customers_per_kg`; mark flat-only ingredients quantity-unavailable
- [x] 1.5 Unit-test demand math (offs, cancelled exclusion, package isolation, confirmation flip) and ingredient scaling / multi-package aggregation

## 2. Snapshot model and writer

- [x] 2.1 Add `MealDemandSnapshot` model with unique `(service_date, meal_period, package)` (nullable package for overall if used), count fields, frozen ingredient JSON, `confirmation_status`, `captured_at` / `confirmed_at`
- [x] 2.2 Migration + admin registration (optional read-only admin)
- [x] 2.3 Implement upsert writer that freezes live demand + ingredients when a slot is confirmed
- [x] 2.4 Add management command (and optional scheduled hook) to confirm-and-save due slots; ensure second run updates rather than duplicates

## 3. Admin statistics API

- [x] 3.1 Add serializers for overall + package-wise meal statistics (including `confirmation_status`)
- [x] 3.2 Implement `GET /api/v1/web/orders/meal-statistics/` with `service_date`, optional `meal_period`, optional package filter; default date = today in meal-off timezone
- [x] 3.3 Wire URL, verified-admin permission, OpenAPI schema/examples
- [x] 3.4 API tests: success filters, both-periods response, auth denial, counts match service

## 4. Kitchen today-requirement API

- [x] 4.1 Implement lean `GET /api/v1/web/orders/kitchen/today-meal-requirement/` using default slot resolver + optional query overrides
- [x] 4.2 Return headcount fields + ingredient list + incomplete-menu flag; keep payload minimal
- [x] 4.3 Wire URL, verified-admin permission, OpenAPI schema/examples
- [x] 4.4 API tests: morning→lunch default, afternoon→dinner default, explicit override, missing menu, auth denial

## 5. History report API

- [x] 5.1 Implement `GET /api/v1/web/orders/meal-history/` reading persisted snapshots (date range, optional package / period filters)
- [x] 5.2 Ensure history returns frozen quantities after catalog yield changes
- [x] 5.3 Wire URL, verified-admin permission, OpenAPI schema/examples
- [x] 5.4 API tests: list/filter, upsert idempotency via writer, customer denied

## 6. Docs and verification

- [x] 6.1 Backend docs (`orders/docs/backend/meal-demand-kitchen-planning.md`) covering formulas, endpoints, filters, confirmation semantics, ingredient math
- [x] 6.2 Frontend/admin docs (`orders/docs/frontend/meal-demand-kitchen-planning.md`) for dashboard metrics and kitchen one-click view
- [x] 6.3 Run targeted tests for meal demand / kitchen / history and fix regressions
