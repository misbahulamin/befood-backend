## Context

### Current production model

Befood’s live delivery ops are **zone-scoped meal slots**, not per-order courier jobs:

```text
RiderProfile ──assigned──► DeliveryZone ──► DeliveryLocation ◄── CustomerProfile
                                                      │
                                                      ▼
                                              OrderDelivery
                                              (scheduled | delivered | skipped | missed)
                                              audit: marked_at, marked_by
```

| Piece | Location | Role today |
|-------|----------|------------|
| Meal slot | `orders.OrderDelivery` | Lunch/dinner fulfillment; wallet charge on deliver |
| Rider | `user_management.RiderProfile` | Auth + zone assignment |
| Zone ops | `delivery_zones` | Priority locations, deliveryman board, admin zone CRUD |
| Mobile mark | `POST /user_management/deliveryman/deliveries/<uuid>/mark/` | Only `delivered` + optional note |
| Admin deliverymen | `/user_management/admin/deliverymen/` | Approve / reject / assign-zone |
| Ops summary | `GET /api/v1/web/delivery-zones/ops/summary/` | Counts for one date + meal period |

Legacy `delivery.DeliveryAssignment` (`assigned` → `picked_up` → `delivered`) exists but is **not mounted** in `core/urls.py` and is not used by the zone board. Do not revive it as the primary write path.

### Product ask

Admin 360° for any Delivery Man: overview card, today/month/lifetime metrics, individual delivery history, timeline, route sequence, richer completion capture, logistics status lifecycle, filters, and ranking — plus frontend page structure docs.

### Constraints

- Multi-client: admin analytics on **web** (`IsVerifiedAdmin`); rider transitions on **mobile** deliveryman APIs
- Keep meal-slot statuses for wallet/skip/miss semantics intact
- Mirror admin-customer-360: **lean overview + lazy paginated sub-resources**
- Prefer durable history over inferring rider from current zone assignment

## Goals / Non-Goals

**Goals:**

- Verified-admin APIs for Delivery Man 360 analytics (list KPIs, overview, history, timeline, route, ranking)
- Persist logistics events and completion metadata on each stop
- Attribute each completed stop to a Delivery Man immutably at mark time
- Fast dashboards via indexes + optional daily summary rows
- Document admin frontend page/tab contract

**Non-Goals:**

- Continuous live GPS tracking / WebSocket location streaming
- Customer-facing ETA or map
- Per-stop dispatch replacing zone assignment
- Rider payroll / incentives
- Mounting or migrating the unused `delivery` app ViewSets
- Frontend implementation in this repo (docs only; UI lives in `befood-frontend`)

## Decisions

### D1 — Two status dimensions (meal vs logistics)

**Decision:** Keep `OrderDelivery.status` as the **meal fulfillment** vocabulary (`scheduled` / `delivered` / `skipped` / `missed`). Introduce a separate **logistics_status** (or sibling model fields) for rider progress:

`assigned` → `accepted` → `picked_up` → `out_for_delivery` → `delivered` | `failed` | `cancelled`

**Rationale:** Meal `skipped`/`missed` drive wallet and kitchen rules; conflating them with rider “failed” would break existing mark/skip flows.

**Alternatives considered:**

- Reuse `DeliveryAssignment` OneToOne-on-Order — rejects subscription-owned slots and dual-parent model
- Expand `OrderDelivery.status` enum with logistics values — **BREAKING** for clients and payment rules

### D2 — Extend `OrderDelivery` + activity log (not new Delivery entity)

**Decision:** Add nullable logistics columns on `OrderDelivery` (and/or a 1:1 `DeliveryLogistics` row) plus append-only `DeliveryActivityLog`:

| Concept | Storage |
|---------|---------|
| Rider who fulfilled stop | `delivered_by_rider` FK → `RiderProfile` (set on successful deliver; immutable thereafter) |
| Zone/location snapshot at mark | `zone_id` / `location_id` snapshots (or FKs + denormalized codes) so history survives reassignment |
| Logistics timestamps | `assigned_at`, `accepted_at`, `picked_up_at`, `out_for_delivery_at`, `delivered_at`, `failed_at` |
| Completion GPS | `completion_latitude`, `completion_longitude` |
| Duration | `delivery_duration_seconds` (computed: prefer `picked_up_at`→`delivered_at`, else `assigned_at`/`out_for_delivery_at`→`delivered_at`) |
| Events | `DeliveryActivityLog(delivery, rider, status, timestamp, lat, lng, source, note)` |

**Rationale:** One row already exists per lunch/dinner stop; analytics join stays simple. Activity log enables timeline without rewriting the slot.

**Alternatives considered:** Full new `DeliveryJob` table — higher migration cost for little gain while zone board still keys off `OrderDelivery`.

### D3 — Lifecycle adoption phases

**Decision:** Ship in two phases behind the same schema:

1. **Phase A (MVP analytics):** On mark-delivered (mobile/admin), set `delivered_by_rider` (zone rider or marking rider), `delivered_at`/`marked_at`, optional GPS, duration if start timestamps exist, activity log `delivered`. Backfill historical `delivered_by_rider` as best-effort NULL or inferred only when zone history is unknown → prefer NULL over wrong attribution.
2. **Phase B (full lifecycle):** Mobile endpoints (or extended mark) for `accepted` / `picked_up` / `out_for_delivery` / `failed`; admin timeline shows all events. Until riders adopt Phase B, admin UI still works with delivered-only timelines.

**Rationale:** Unblocks 360 dashboards without forcing an immediate mobile UX rewrite.

### D4 — Admin API shape and mounting

**Decision:** Add web routes under `/api/v1/web/delivery-men/` (kebab-case resource) for analytics, while keeping existing `/user_management/admin/deliverymen/` for approval/zone assignment (or thin aliases). Follow customer-360:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/web/delivery-men/` | List: identity + zone + today/month/lifetime counts |
| `GET /api/v1/web/delivery-men/{public_id}/` | Lean overview card + today/month/lifetime metrics (**no** history arrays) |
| `GET .../{public_id}/deliveries/` | Paginated history + filters |
| `GET .../{public_id}/timeline/` | Activity events for date (default today) |
| `GET .../{public_id}/route/` | Ordered stops for `service_date` + `meal_period` |
| `GET /api/v1/web/delivery-men/rankings/` | Comparison metrics for a period |

Identify riders by `RiderProfile` / user `public_id` consistently with existing admin deliverymen APIs.

**Rationale:** Separates “HR/approval” from “ops analytics”; matches frontend mental model from the requirement.

### D5 — Daily summary table

**Decision:** Introduce `DeliveryManDailySummary` (`rider`, `date`, lunch/dinner/total completed, failed, avg duration, zones covered count) updated in the same transaction as mark/fail transitions (or via post-commit task with idempotent upsert).

**Rationale:** Lifetime/month dashboards must not scan tens of thousands of `OrderDelivery` rows per page load.

**Alternatives considered:** On-the-fly aggregation only — acceptable for short ranges, too slow for lifetime at scale.

### D6 — Filters and ranking metrics

**Decision:** Allowlist query params: date presets (`today`, `yesterday`, `this_week`, `this_month`) or `date_from`/`date_to`; `meal_period`; `zone_public_id`; logistics or meal `status` (document which dimension). Ranking metrics: total deliveries, average delivery time, completion rate, failed count — computed from summaries + logs for the selected window.

### D7 — Route / map payload

**Decision:** Backend returns **sequence data** (hub placeholder + ordered customers with lat/lng snapshots, sequence number, status). Map polyline rendering is frontend-only. Order = zone location `priority` then stable tie-breaker (customer name / delivery id), matching the deliveryman board.

### D8 — Permissions & privacy

**Decision:** All 360 endpoints require `IsVerifiedAdmin`. Rider APIs remain scoped to own zone. Never expose other riders’ boards to a deliveryman. Completion GPS is admin-visible; do not put precise trails on customer APIs.

## Risks / Trade-offs

- **[Risk] Historical attribution wrong after zone reassignment** → Mitigation: snapshot `delivered_by_rider` + zone/location at mark; leave pre-migration rows with NULL rider rather than guessing
- **[Risk] Dual status confuses clients** → Mitigation: document meal vs logistics clearly in OpenAPI; serializers nest `meal_status` and `logistics_status`
- **[Risk] Phase B unused by mobile app** → Mitigation: Phase A still powers history/KPIs from mark-delivered; timeline may be sparse until app ships transitions
- **[Risk] Summary drift** → Mitigation: transactional upsert on transitions; admin rebuild command for a date range
- **[Risk] Performance on unfiltered lifetime history** → Mitigation: require pagination; default date window (e.g. current month) on list endpoints where appropriate; indexes on `(delivered_by_rider, service_date, meal_period, status)`
- **[Trade-off] Not using legacy `delivery` app** → Cleaner ops model, but abandons unused assignment tables (can delete/archive later)

## Migration Plan

1. Add nullable logistics columns + `DeliveryActivityLog` + `DeliveryManDailySummary` migrations (non-blocking, default NULL)
2. Deploy mark-path writers (Phase A) — old mobile clients keep working without GPS
3. Ship admin 360 read APIs + OpenAPI
4. Backfill daily summaries from existing `delivered` rows where `marked_at` exists (rider NULL unless safely inferable)
5. Optional Phase B mobile transition endpoints
6. Frontend consumes docs; feature-flag new pages if needed
7. **Rollback:** stop writing new columns; reads tolerate NULL; drop tables only after feature flag off (columns can remain)

## Open Questions

1. Should admin mark-delivered also set `delivered_by_rider` to the zone’s assigned rider (even when an admin clicks mark), or only when the rider marks via mobile?
2. Exact identifier for list/detail: prefer existing deliveryman admin `public_id` field name — confirm against current serializer.
3. Is `failed` logistics status allowed while meal status stays `scheduled` (retry later), or must fail also skip/miss the meal slot?
4. Does ranking include inactive/unassigned riders or only zone-assigned + verified?
5. Timezone for “today” / “this month”: confirm Asia/Dhaka (or project `TIME_ZONE`) for all presets.
