## Context

BeFood Express already runs on zone-scoped `OrderDelivery` stops:

- Auth: verified `RiderProfile` + `IsVerifiedDeliveryman`
- Scope: `DeliveryZone.assigned_delivery_man` → customer `delivery_location.zone`
- Board: `GET /user_management/deliveryman/deliveries/today-board/` via `build_deliveryman_board` (active meal window from `get_current_delivery_period`, Asia/Dhaka)
- Mark: `POST .../deliveries/{public_id}/mark/` → `mark_delivery_and_notify` (wallet charge, Onahar/referral best-effort, logistics Phase A attribution)
- History is not deleted: default board filters `status=scheduled`; `include_delivered=true` already exists but is insufficient for tabs + metrics UX
- Package display today: `meal_name` = `meal_name_snapshot`; mobile UI concatenates with `menu_items_label` and shows `status` as “নির্ধারিত”
- Admin 360 (`delivery-man-360-analytics`) already has rider KPIs for **admins**; riders have no self-service today summary
- Customer activity `meal_delivered` exists but omits Delivery Man identity

Stakeholders: Delivery Man mobile (later), ops admins reading customer activity, backend maintainers.

## Goals / Non-Goals

**Goals:**

- Rider can fetch **pending** and **delivered** lists for business today / active meal window without losing completed rows
- Rider can fetch **today summary**: total, delivered, pending, plus dynamic package breakdown
- Board rows expose structured package fields while keeping existing keys
- Customer activity `meal_delivered` includes Delivery Man when known
- Preserve zone authorization, mark idempotency, and meal-off timezone semantics
- Backward compatible with current Flutter app

**Non-Goals:**

- Rewriting or replacing zone-based delivery / mark / wallet charge
- Flutter UI implementation in this change
- New delivery status enums or parallel delivery tables
- Admin 360 redesign
- Multi-zone riders, per-stop dispatch, live GPS streaming
- Counting rules based on meal quantity as primary “delivery count” (stops remain the unit unless documented otherwise)

## Decisions

### D1 — Reuse `OrderDelivery.status`; no new tables for pending/delivered

**Decision:** Pending = `scheduled`, Delivered = `delivered` on existing slots. Do not add a second “delivery history” entity.

**Why:** Rows already persist after mark; disappearance is query filtering only.

**Alternatives:** Soft-delete / archive table — rejected (breaks wallet, 360, kitchen parity).

### D2 — Status filter on today-board + dedicated summary endpoint

**Decision:**

1. Extend today-board with a documented `status` query (or formalize `include_delivered` into exclusive modes):
   - default / `status=scheduled` → To Deliver (current behavior)
   - `status=delivered` → Delivered tab only
   - optional `status=all` if useful for debugging (not required for mobile tabs)
2. New `GET /user_management/deliveryman/deliveries/today-summary/` for counts + package breakdown (aggregation without shipping full lists twice)

**Why:** Tabs need exclusive lists; metrics need cheap aggregates. Prefer additive endpoint over stuffing heavy aggregates into every board poll.

**Alternatives:** Only `include_delivered` — rejected (ambiguous for Delivered-only tab). Client-side filter of full board — rejected (bandwidth + wrong totals if pending-only default).

### D3 — Metrics scope = same as board (zone + business today + active meal period)

**Decision:** Summary uses identical scoping as `build_deliveryman_board`: assigned zone, `get_current_delivery_period()`, exclude low-balance blocked customers, live subscription/order parents.

**Count unit:** `delivery_count` = number of `OrderDelivery` stops (same as board `total_count` / location `delivery_count`). Optionally expose `meal_quantity_sum` as additive field if cheap; primary KPIs use stop counts so tabs and summary stay consistent.

**Delivered attribution for “my delivered” list:** Prefer zone-scoped delivered stops for the rider’s zone (matches “my assigned work today”). When showing Delivered tab, include zone delivered rows for the window; if `delivered_by_rider` is set to another rider (admin mark edge case), still show in zone board but summary docs note attribution fields. Do **not** show other zones’ deliveries.

### D4 — Package breakdown from snapshots + MealCategory public_id when available

**Decision:** Group by:

- `package_name` ← `subscription.meal_name_snapshot` or `order.meal_name_snapshot`
- `package_public_id` ← related `meal.public_id` when select_related available; null if missing

Aggregate with DB `values().annotate(Count)` over the same queryset as summary totals — avoid loading all rows into Python when possible.

**Why:** Snapshots stay historically stable; live MealCategory rename must not rewrite past board labels. Hardcoded package names forbidden.

### D5 — Additive board row fields; keep `meal_name` / `status`

**Decision:** Add to each customer row (when known):

- `package_name` (same source as today’s `meal_name`)
- `package_public_id` (nullable)
- For delivered rows: `delivered_at` (prefer logistics `delivered_at`, else `marked_at`), `delivered_by_rider_public_id`, `delivered_by_name` (nullable)

Keep `meal_name`, `menu_items_label`, `status`, `meal_period`, `meal_quantity` unchanged so current app keeps working. Mobile later can prefer `package_name` + `menu_items_label` and de-emphasize status chip.

### D6 — Mark Delivered: reuse existing attribution; enrich customer activity only

**Decision:** No new `delivered_by` User FK. Continue `marked_by` + `delivered_by_rider` + `delivered_at` from Phase A logistics. Inside the same mark transaction path, activity remains a **composed read model** — update `build_activity_events` to include rider identity in `meal_delivered` summary/refs. No separate activity insert table required.

**Why:** Customer activity is already composed from `OrderDelivery`; writing a duplicate event store would diverge. Rider identity is already on the delivery row after Phase A.

**Idempotency:** Keep current `select_for_update` + same-status short-circuit (200 without double charge). Terminal conflicts stay 409.

### D7 — Authorization unchanged

**Decision:** All new endpoints use `IsVerifiedDeliveryman` + `zone_for_rider` / `delivery_in_rider_zone`. Reject foreign `zone_public_id` / date overrides the same way board already ignores client date/period.

### D8 — Timezone

**Decision:** Always `get_meal_off_settings().timezone` (default Asia/Dhaka) via `get_current_delivery_period`. Never `date.today()` from server local alone.

## Risks / Trade-offs

- **[Risk] Delivered tab empty after mark if client still polls default board** → Mitigation: document `status=delivered` (or dedicated mode); summary endpoint for KPIs regardless of tab
- **[Risk] Package rename vs snapshot mismatch** → Mitigation: breakdown uses snapshots; `package_public_id` optional for grouping stability
- **[Risk] Admin-marked deliveries lack rider** → Mitigation: Phase A already attributes zone assignee when possible; activity shows rider only when `delivered_by_rider` set
- **[Risk] Quantity vs stop count confusion** → Mitigation: document stop-based totals; optional quantity sum field
- **[Risk] N+1 on package/menu** → Mitigation: reuse board `select_related`; summary uses aggregation queries
- **[Trade-off] Separate summary call** → Extra request for mobile home header; cheaper than dual full-board fetches

## Migration Plan

1. Ship additive API fields + summary endpoint + activity enrichment (no schema migration expected if logistics fields already present from `0017_deliveryman_360_logistics`)
2. Deploy backend; existing mobile continues on default board
3. Later Flutter update consumes summary + status filter + `package_name`
4. Rollback: revert deploy; no destructive migrations

If a gap is found (e.g. missing index on `(service_date, status)` under load), add a **non-blocking** index migration in a follow-up task after measuring.

## Open Questions

- Exact query param name: prefer `status=scheduled|delivered` over expanding `include_delivered` boolean — confirm during apply (lean toward `status` for exclusive tabs; keep `include_delivered` working for backward compat)
- Whether Delivered tab should filter `delivered_by_rider=self` vs all zone delivered (lean: all zone delivered for operational “finished stops in my area”; attribution fields show who marked)
- Whether `meal_quantity_sum` is required in v1 summary (default: omit unless product insists)
