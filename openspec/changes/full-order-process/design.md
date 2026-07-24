## Context

`orders` already supports meal-package purchase: `Order` with snapshots, month lock, status history, customer create / my-orders / cancel / current-package, and Django admin list filters. What is missing is the **operational middle**: generating expected delivery slots, marking deliveries, auto-closing packages by type rules, and an **admin API** to list/filter successful orders with progress.

Meal cycle costing already defines **2 meals per day** and `total_meals_for_month` → **60** (30-day months) or **62** (31-day months). Monthly menu schedule uses `lunch` / `dinner` periods. Order delivery tracking must align with those conventions so kitchen and admin share one calendar language.

Stakeholders: verified customers (place + track own orders), admins/kitchen (list, filter, mark delivered), and the existing meals schedule/pricing layer (read-only dependency for expected counts).

## Goals / Non-Goals

**Goals:**

- End-to-end lifecycle: place order → visible to admin → activate in window → track deliveries → complete / cancel.
- Delivery expectations by package type (daily one-shot; multi-day packages 2×/day; monthly totals 60/62).
- Admin paginated list/detail with filters: meal type, status / active-inactive, order month, date range; include delivery progress counters.
- Customer visibility of own order delivery progress.
- Services-layer orchestration (`orders/services/`), thin views, tests, and beginner-friendly backend docs.

**Non-Goals:**

- Payment provider capture/refund flows.
- Live courier tracking / maps.
- Reworking cart / multi-outlet POS checkout.
- Changing meal cycle cost formulas or menu-schedule quota rules.
- Auto-assigning menu ingredients onto delivery slots (schedule remains meals-owned).

## Decisions

### 1. Model: `OrderDelivery` slots (not mutate OrderItem)

**Choice:** Add `OrderDelivery` with `(order, service_date, meal_period)` unique, status (`scheduled` | `delivered` | `skipped` | `missed`), timestamps, and `marked_by`.

**Why:** Order is the commercial package; deliveries are the operational units. Keeps history and progress queries simple without overloading `OrderStatusHistory`.

**Alternatives:** Only bump a counter on `Order` — rejected (no lunch/dinner audit, cannot mark individual slots). Reuse menu schedule slots — rejected (schedule is kitchen plan, not per-customer fulfillment).

### 2. Expected slot generation at order create

**Choice:** After `create_meal_order`, generate all expected `OrderDelivery` rows for the order period:

| meal_type | slots |
|-----------|--------|
| `daily` | **1** slot on `order_start_date` (`meal_period=lunch` by default) |
| `weekly` | each day in `[start, end]` × **lunch + dinner** (14 for 7 days) |
| `half_monthly` | each day × 2 |
| `monthly` | each calendar day of the month × 2 → **60 or 62** via `total_meals_for_month` / day count × 2 |
| longer types (`six_months`, `yearly`) | same 2×/day rule across the order window (generate lazily by month batch if row count is large — see risks) |

**Why:** Matches user rules for daily vs monthly and reuses existing month meal math. Weekly/half-monthly follow the same 2×/day kitchen cadence unless product later splits them.

**Alternatives:** Generate slots lazily on first admin open — rejected (harder progress % and month filters). One delivery per day for weekly — deferred; product can tighten later without changing the admin API shape.

### 3. Lifecycle transitions

**Choice:** Keep existing `Order.OrderStatus` enum. Add service rules:

- Create → `confirmed` (unchanged).
- Activate → `active` when `today >= order_start_date` (job or on-read / on mark-delivery entry).
- Complete → `completed` when:
  - **daily:** first delivery marked `delivered` (or all expected slots terminal), or
  - **multi-day:** all expected slots are terminal (`delivered`/`skipped`/`missed`), or `today > order_end_date` with remaining `scheduled` flipped to `missed` then order completed.
- Cancel remains owner/admin before start (existing rules); cannot cancel once deliveries have started unless admin force-cancel (out of default customer path).

**Why:** Minimal **BREAKING** surface; status history already exists.

### 4. Active vs inactive filter semantics

**Choice:** Admin filter `activity=active|inactive`:

- **active:** `order_status` in (`confirmed`, `active`) AND `order_start_date <= today <= order_end_date` (or `order_status=active`).
- **inactive:** `completed`, `cancelled`, or outside the date window while not active.

Also keep raw `order_status`, `meal_type` (`meal_type_snapshot`), `order_month`, `created_after` / `created_before`, `start_date` / `end_date` range filters.

### 5. API surface (multi-client)

**Choice:**

- Keep customer routes under existing `/api/v1/orders/...` (additive: delivery progress on detail / optional nested list).
- Add **web/admin** routes under `/api/v1/web/orders/` (list, retrieve, mark delivery, bulk “today’s deliveries”) with `HasGroupPermission` / verified admin.
- Mark delivery: `POST /api/v1/web/orders/{id}/deliveries/{delivery_id}/mark` with `{ "status": "delivered" | "skipped", "note": "" }`.

**Why:** Aligns with multi-client rule — operators/admins get management payloads; customers stay lean.

### 6. Month package “week active for current month days”

**Choice:** For monthly (and multi-day) packages, admin/customer progress responses include:

- `expected_deliveries`, `delivered_count`, `remaining_count`
- `active_days_this_month`: distinct `service_date` values in the current calendar month still `scheduled` or already `delivered` within the order window
- optional `week_of_month` query on admin “today board” to focus one ISO week

**Why:** Satisfies “week active for this current month days” without a separate product entity.

### 7. Permissions & scope

**Choice:** Customers only see own orders (existing). Admins see all non-sensitive fields needed for ops (customer id/email, package snapshots, delivery progress). Object-level checks on mark-delivery. Never trust client-supplied customer id for ownership.

## Risks / Trade-offs

- **[Risk] Large slot generation for yearly packages** → Mitigation: for `six_months`/`yearly`, generate current month’s slots eagerly and remaining months via management command / on month boundary; still expose expected total from duration math.
- **[Risk] Clock skew / timezone for activate-complete** → Mitigation: use `timezone.localdate()` consistently (same as order duration / menu reveal).
- **[Risk] Concurrent double mark-delivered** → Mitigation: `select_for_update` on delivery row + idempotent “already delivered” → 409 or 200 with same state.
- **[Risk] Daily default period `lunch` may not match kitchen** → Mitigation: document default; allow admin override period only before mark if product needs (optional field on generate).
- **[Trade-off] Weekly = 2×/day assumed** → Documented; changeable via expected-count strategy without rewriting admin filters.

## Migration Plan

1. Add `OrderDelivery` model + migration; backfill: for existing non-cancelled orders, generate remaining slots from `today` forward (past days as `missed` or skip backfill past — prefer generate full window with past `scheduled` → `missed` on activate job).
2. Deploy APIs behind admin permission; customer detail gains progress fields (additive).
3. Optional management command `sync_order_lifecycle` for activate/complete sweeps.
4. Rollback: remove new routes; keep delivery table (safe orphan) or reverse migration if unused.

## Open Questions

- Should daily packages use a single `meal_period=once` enum value instead of defaulting to `lunch`? (Defaulting to `lunch` for now.)
- Should customer be allowed to self-confirm receipt, or admin-only mark-delivered? (**Default: admin/kitchen only** for mark; customer read-only progress.)
- Exact permission codenames for web order admin (reuse existing admin group vs new `orders.manage_orders`) — implement against project’s `HasGroupPermission` patterns at apply time.
