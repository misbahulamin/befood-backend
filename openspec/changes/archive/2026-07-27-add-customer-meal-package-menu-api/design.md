## Context

Operators already build and publish a full monthly lunch/dinner menu per meal package via `MonthlyMenuSchedule` (admin APIs under `/meals/menu-schedules/`). Customers own a package through `Order` (`Order.meal` → `MealCategory`). The only customer menu read today is `GET /meals/today-menu/`, which applies reveal-time gating and returns only the current day's visible periods.

Stakeholders: verified customers (mobile/web) who need to browse the full month menu for their purchased package; existing today-menu and admin schedule flows must stay unchanged.

Constraints:
- Reuse existing models — no new tables.
- Follow customer auth pattern `IsVerifiedCustomer` + Token auth.
- Keep customer payloads lean (IDs + display labels + ingredients), not admin quota/assignment editor shapes.
- Mount under existing `/meals/` routes (project does not put customer meal APIs under `/api/v1/` today).

## Goals / Non-Goals

**Goals:**
- Let an authenticated verified customer retrieve the full published monthly menu (all service dates × lunch/dinner slots with ingredients) for their active meal package(s).
- Resolve package from the customer's non-cancelled order(s) for the target month.
- Return a clear empty/unpublished state when there is no package or the schedule is not published yet.
- Document and test the contract.

**Non-Goals:**
- Changing admin menu schedule CRUD, publish/unpublish, or sync flows.
- Changing `today-menu` reveal-time behavior.
- Letting customers edit menus or see draft/unpublished schedules.
- Exposing other customers' packages or cross-package browsing by arbitrary meal IDs.
- Historical multi-month archive browsing beyond a simple optional year/month filter for the customer's own order month.

## Decisions

### 1. Endpoint shape
- **Choice:** `GET /meals/my-package-menu/` as an `APIView` next to `CustomerTodayMenuView`.
- **Rationale:** Matches existing customer menu mounting (`today-menu`); resource-oriented “my package menu” without verbs in nested paths; avoids overloading admin `menu-schedules` ViewSet.
- **Alternatives considered:**
  - `GET /orders/current-package/menu/` — couples menu read to orders app; menu data lives in `meals`.
  - Nested action on meal detail — would require clients to know `meal_public_id` and risk leaking menus without ownership checks unless carefully gated.

### 2. Package resolution
- **Choice:** Load non-cancelled orders for the authenticated customer covering the target month (default: current local month via `order_month` / active date range), same spirit as `get_current_package` / `active_orders_for_customer_on_date`. For each order, load the published `MonthlyMenuSchedule` where `plan.meal_category == order.meal` and `plan.cycle` matches the order's year/month.
- **Rationale:** Menu depends on the package the customer actually bought; mirrors today-menu ownership join.
- **Alternatives considered:**
  - Require client to pass `meal_public_id` only — insecure if not ownership-checked; unnecessary when order already implies the meal.
  - Always exactly one package — today-menu already supports multiple active packages; keep array `packages` for consistency.

### 3. Reveal-time vs full calendar
- **Choice:** Full monthly menu returns **all published slots** without lunch/dinner reveal-time gating.
- **Rationale:** Product ask is a full-month calendar so customers can plan ahead; reveal rules remain for `today-menu` only.
- **Alternatives considered:** Apply reveal rules to future days too — would defeat “see full month menu.”

### 4. Query parameters
- **Choice:** Optional `year` + `month` (integers) to select which calendar month's menu to load for the customer's order in that month. Default = current business/local month. Reject invalid combinations with `400`.
- **Rationale:** Supports “view this month's package menu” without a new resource ID; still scoped to the caller's orders only.
- **Alternatives considered:** `order_public_id` filter — useful later; defer to keep v1 simple unless needed in apply.

### 5. Response payload
- **Choice:** Top-level `{ year, month, packages: [...] }`. Each package includes `meal_public_id`, `meal_name`, `order_public_id`, `schedule_published`, and `days` (or `slots`) as a list of `{ service_date, meal_period, ingredients: [{ id, name, product_role }] }` ordered by date then period — reuse the ingredient shape from `serialize_schedule_assignments` / today-menu.
- **Rationale:** Familiar field names for clients already using today-menu; omit admin-only fields (`quota_summary`, plan costing, internal PKs beyond ingredient id already used).
- **When unpublished / missing schedule:** `schedule_published: false`, `days: []`, still return package identity so UI can show “menu coming soon.”
- **When no active order:** `packages: []` with `200` (same pattern as empty today-menu / current-package null messaging optional in `message`).

### 6. Service layer
- **Choice:** Add `build_package_menu_for_customer(customer_profile, *, year=None, month=None)` in `meals/services/` (new module e..g. `package_menu.py` or extend `today_menu.py` only if shared helpers stay cohesive). Views stay thin.
- **Rationale:** Matches django-drf-conventions; reuses schedule serialization helpers where practical.

### 7. Auth / permissions
- **Choice:** `IsVerifiedCustomer` (same as today-menu). Unauthenticated → `401`. Non-customer authenticated without profile → empty or `403` consistent with today-menu.
- **Rationale:** Customer-only data; package ownership enforced by querying the caller's orders only (BOLA-safe: never accept another customer's order id as authoritative without ownership).

### 8. Docs & OpenAPI
- **Choice:** `extend_schema` on the view; frontend doc `meals/docs/frontend/customer-package-menu.md`; backend note `meals/docs/backend/customer-package-menu.md`.
- **Rationale:** Project documentation rules for new customer API contracts.

## Risks / Trade-offs

- **[Risk] Large monthly payloads (31 days × 2 periods × N ingredients)** → Mitigation: lean ingredient fields only; prefetch slots/items; consider client caching; pagination not required for one month.
- **[Risk] Customers see future meals earlier than operators intended** → Mitigation: intentional product decision; operators control visibility via publish/unpublish; today-menu still gated for “what's served now.”
- **[Risk] Order month vs cycle month mismatch for non-monthly meal types** → Mitigation: resolve schedule by cycle year/month derived from the order's service window / `order_month`; document that menu covers the cycle month of the package.
- **[Risk] Duplicate logic with today-menu** → Mitigation: share schedule lookup and ingredient serialization helpers; keep reveal logic only in today-menu path.

## Migration Plan

1. Ship additive endpoint + service + tests + docs (no DB migration).
2. Clients adopt `GET /meals/my-package-menu/` for calendar UI; keep calling `today-menu` for daily reveal.
3. Rollback: remove route/view only; no data migration required.

## Open Questions

- None blocking implementation. Optional follow-up: filter by `order_public_id` if multi-package months become common.
