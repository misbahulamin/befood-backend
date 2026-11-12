# Design

## Context

See `proposal.md` for motivation. Today:

- `delivery_zones.services.ops.build_ops_summary` aggregates **one** `service_date` + `meal_period` by Zone → Location → Sub-location using live customer sub-location (and rider from zone assignment).
- `user_management.services.churn.build_churn_analytics` computes period KPIs/breakdowns but **does not** emit geo slices (even though an in-flight churn delta mentioned zone/location).
- Customers carry `delivery_sub_location` (location/zone derived). `OrderDelivery` may carry `logistics_sub_location` for durable stop attribution when stamped.

Geo analytics must reuse lifecycle helpers (`orders.services.customer_lifecycle`) and churn period-bound patterns (Asia/Dhaka, max 366 days) without replacing day ops or global churn screens.

## Goals / Non-Goals

**Goals:**

- One admin-facing analytics service that builds a hierarchical matrix + rankings for a date range.
- Consistent attribution rules documented for customers (current assignment) vs meals (prefer `logistics_sub_location`, else customer sub-location at query time).
- Thin DRF views under web delivery-zones URLs; business logic in `delivery_zones/services/`.
- Frontend docs that distinguish ops vs analytics and map drill-downs to existing customer/churn list filters.

**Non-Goals:**

- Pre-aggregated warehouse tables / nightly rollups in v1 (optimize later if slow).
- Map/GIS tiles, CSV export, mobile rider endpoints.
- Changing assignment, board, or day `ops/summary` contracts.
- Implementing Admin Panel React code in this repo.

## Decisions

### 1. Endpoint shape: matrix + rankings under delivery-zones analytics

- **Choice:** `GET /api/v1/web/delivery-zones/analytics/matrix/?from=&to=&meal_period=&zone_public_id=&location_public_id=&sub_location_public_id=`
- Optional sibling: `GET /api/v1/web/delivery-zones/analytics/rankings/?…` **or** include `rankings` in the same payload if response size stays acceptable for typical zone counts.
- **Why:** Keeps geo ops and geo analytics discoverable next to existing `/delivery-zones/ops/summary/`. Avoids overloading churn analytics (global product metrics) with a full hierarchy tree.
- **Alternative considered:** Extend only `/churn/analytics/` — rejected because meal volume + rider workload are delivery-ops concerns, not churn-only.

### 2. Attribution rules

| Metric family | Attribution |
|---------------|-------------|
| Customer density / lifecycle splits | Current `CustomerProfile.delivery_sub_location` → location → zone |
| Period churn | Churned subscriptions in `[from, to]` joined to customer’s **current** geo (document as “current assignment”; historical geo snapshot out of scope for v1) |
| Meal volume | Prefer `OrderDelivery.logistics_sub_location`; fallback to subscription/order customer sub-location (same pattern as ops summary) |
| Rider workload | Zone’s primary `assigned_delivery_man` + summed zone volume for the period |

- **Why:** Matches how ops already groups stops; avoids inventing historical assignment tables in v1.
- **Trade-off:** Customers who moved zones after cancel will show churn under the **new** area. Document clearly; future work can snapshot geo on cancel if needed.

### 3. Service module layout

- Add `delivery_zones/services/geo_analytics.py` (parse/allowlist query, build matrix, rankings).
- Reuse: `business_calendar` / Dhaka date helpers from churn or shared utils; `annotate_lifecycle` / lifecycle constants; `live_delivery_q` or equivalent for counting deliveries in range.
- Views: thin APIView(s) with `IsVerifiedAdmin`, OpenAPI helpers alongside existing zone web views.
- Tests: extend `delivery_zones/tests/` with matrix + ranking + auth + filter cases; seed small zone/location/sub-location trees.

### 4. Ranking thresholds

- Highest churn ranking excludes nodes with `active_at_period_start < 5` (configurable constant in service, documented).
- Density rankings use assigned customer total; meal rankings use delivered or total (document which; prefer `delivered` for “volume served”, expose `total` as well on nodes).

### 5. Performance approach (v1)

- Build with grouped `values().annotate(Count)` / in-memory bucket merge similar to ops summary (zone counts are small).
- Cap range at 366 days (same as churn).
- If production latency regresses, follow-up change can add daily geo summary tables—out of scope now.

### 6. Frontend docs + customer prompt

- Update/add `delivery_zones/docs/frontend/` geo analytics section (and backend tech notes under `docs/backend/`).
- After implementation, hand the customer a single Admin Panel prompt covering geo analytics plus recently shipped delivery/churn contracts (prompt lives in chat / ops handoff, not as runtime code).

## Risks / Trade-offs

- **[Risk] Current-assignment churn skew** → Mitigation: document in API + frontend docs; optional later snapshot on cancel.
- **[Risk] Heavy queries over long ranges** → Mitigation: 366-day cap, indexed FKs already on sub-location; add timings in tests with modest fixtures; revisit aggregates if needed.
- **[Risk] Dual truth vs churn analytics** → Mitigation: geo churn counts are scoped slices; global churn KPIs remain on `/churn/analytics/`; docs tell FE which screen owns which metric.
- **[Risk] Incomplete `logistics_sub_location` backfill** → Mitigation: fallback to customer sub-location; report unassigned delivery count like ops.

## Migration Plan

1. Ship additive endpoints + docs (no schema break).
2. No data migration required for v1 beyond relying on existing sub-location / logistics FKs.
3. Rollback: unroute analytics URLs; no destructive migrations.

## Open Questions

- Whether rankings ship in the same response as the matrix or a sibling path (default: same response with a `rankings` object unless payload size forces a split during implement).
