# Design

## Context

Observed backend gaps (code evidence, not screenshot assumptions):

- `user_management/services/admin_dashboard.py` sets `total_meals_served` / `monthly_meals_served` / `today_delivery` via `OrderDelivery.objects.filter(status=delivered).count()` — **delivery-stop counts**, ignoring Guest Meal `quantity`.
- Regular profit recognition lives in `admin_wallet/services/profit_ledger.recognize_meal_profit`, hooked from `orders/services/meal_payment.charge_delivered_meal`, and is **OneToOne** on `OrderDelivery` (`MealProfitTransaction.order_delivery`).
- Guest prepaid debit happens at `create_guest_meal_order`; `sync_guest_meals_for_delivered_delivery` only flips `GuestMealOrder.status` to `delivered` and does **not** call profit recognition.
- Admin Profit analytics (`admin_wallet/services/profit_analytics.py`) aggregates only `MealProfitTransaction` rows, so guest boxes never appear in lifetime/month/today/range/history/chart.
- Admin Guest Meals summary `summarize_admin_guest_meals` exposes `revenue` as `Sum(total_amount)` across statuses — prepaid order value, not realized delivered revenue.
- Frontend lives at `F:\befood\Software\befood-frontend` (`/admin/dashboard`, `/admin/profit`, `/admin/guest-meals`).
- Constraint from product: additive changes only — do not arbitrarily rewrite existing regular-meal accounting.

See `proposal.md` for motivation and capability list.

## Goals / Non-Goals

**Goals:**

- One ledger-backed reporting path where delivered guest boxes contribute to meals served, realized revenue, cost, and profit.
- Idempotent guest realization on the existing mark-delivered sync hook.
- Additive API fields so current clients keep working.
- Safe dry-run historical reconcile for already-delivered guest orders.
- Frontend consumes backend totals; no client-side substitute ledger.

**Non-Goals:**

- Changing Guest Meal purchase/wallet debit rules or inventing cancel/refund.
- Treating `box_price` as packaging COGS.
- Recomputing historical regular `MealProfitTransaction` rows.
- Rewriting kitchen/rider modules beyond consistency checks.
- Implementing production backfill without an explicit operator apply flag / approval.

## Decisions

### 1. Extend `MealProfitTransaction` for Guest Meal rows (same ledger)

**Choice:** Keep one ledger table used by `profit_analytics`, and add guest-capable rows rather than a parallel aggregation path.

**Schema approach (additive):**

- Add nullable `guest_meal_order` OneToOne (`PROTECT`, unique) → at most one realization per Guest Meal order.
- Add `meal_kind` (`regular` | `guest`) with default `regular` for existing rows.
- Add `quantity` (default `1`) so guest qty is stored explicitly.
- Relax `order_delivery` from OneToOne to FK (`PROTECT`): one delivery may have **one regular** row (existing) plus **N guest** rows (one per GuestMealOrder). Enforce uniqueness for regular rows with a partial unique constraint on `order_delivery` where `meal_kind=regular` (and/or `guest_meal_order IS NULL`).
- Add source value(s) such as `guest_delivery` / reuse `backfill` for reconcile.

**Alternatives considered:**

- Separate `GuestMealProfitTransaction` table → duplicates analytics filters/history serializers.
- Fold guest revenue into the single regular delivery row → loses distinguishability, breaks OneToOne semantics for retries, and mixes prepaid guest with charged regular amounts.

### 2. Recognition hook placement

**Choice:** Call `recognize_guest_meal_profit(guest_order)` from `sync_guest_meals_for_delivered_delivery` (or immediately after it inside the same `mark_delivery` atomic transaction) after status updates to `delivered`.

**Rationale:** All mark-delivered paths (admin, rider, auto) already converge on `mark_delivery` → guest sync. Do **not** hook inside `charge_delivered_meal` for guest amounts (guest is prepaid; charge path is regular-only).

**Idempotency:** create-or-get by `guest_meal_order_id` unique constraint + IntegrityError recovery (same pattern as current delivery OneToOne).

### 3. Guest financial formulas

Using published slot snapshots for the guest order’s package / `service_date` / `meal_period`:

- `meal_price` (revenue) = `GuestMealOrder.total_amount`
- `food_cost` = `quantity × ingredient_cost_snapshot` (or `0.00` if missing)
- `operational_cost` = `quantity × operational_cost_snapshot` (or `0.00` if missing)
- `profit_amount` = `meal_price - food_cost - operational_cost` (quantized)

**Why not `quantity × profit_snapshot`?** Regular rows store published `profit_snapshot` because regular revenue is the charged meal price already aligned with that publish math. Guest revenue includes `box_price` markup; using only `profit_snapshot × qty` would understate guest margin and ignore prepaid total. Computing profit from stored revenue − attributable costs keeps reconciliation equations honest and still uses immutable published cost snapshots (not live catalog prices).

**Explicit non-decision:** no packaging COGS derived from `box_price`.

### 4. Dashboard meals-served semantics

**Choice:** Make food-box metrics explicit and additive; keep stop metrics separate.

| Field | Meaning |
|---|---|
| `today_delivery` | unchanged — delivered **stops** today |
| `regular_meals_served` / `guest_meals_served` / `total_meals_served` | delivered food boxes (guest uses `Sum(quantity)`) |
| month variants | same, filtered by Asia/Dhaka month-to-date `service_date` |

**Compatibility note:** Today `total_meals_served` is stop count. Changing it to food boxes is a **semantic** change for that key. Prefer:

1. Add `regular_meals_served`, `guest_meals_served`, and set `total_meals_served = regular + guest` (food boxes), **and**
2. Add `total_delivery_stops` (lifetime) / keep `today_delivery` as stops so UI can preserve stop cards.

Document the semantic upgrade for `total_meals_served` in frontend/backend docs. This matches the product formula the admin expects for that card title (“Meals Served”).

### 5. Profit API additive breakdown

Extend `dashboard_payload` / serializers with optional additive keys, e.g.:

- `regular_revenue`, `guest_revenue`, `range_revenue` (total)
- same pattern for food cost / profit / meals served / `range_deliveries` remains ledger-aware but document whether it means ledger rows or stops — prefer keep `range_deliveries` as count of ledger rows **or** introduce `range_delivery_stops` / `range_meals_served` additively without breaking the existing key meaning used by UI.

History serializer: expose `meal_kind`, `quantity`, and guest order public id when present.

### 6. Guest Meals admin summary

Keep legacy `revenue` = prepaid `Sum(total_amount)` for compatibility. Add:

- `prepaid_order_value` (alias/same value, clearer name)
- `delivered_recognized_revenue` (from ledger guest rows in scope, or delivered order totals once realized)
- optional `realized_guest_profit`

Frontend relabels cards accordingly.

### 7. Frontend (separate repo)

After backend reconciliation:

- Dashboard: bind meals-served cards to new totals; optional Regular/Guest micro-breakdown; do not change Catalog card.
- Profit: bind overview/chart/history to additive backend fields; show guest markers in history.
- Guest Meals: rename labels for prepaid vs realized.

No frontend-only formula to “fix” missing backend guest rows.

### 8. Historical reconcile command

Mirror `backfill_meal_profit.py` style:

- `--dry-run` default or required flag pair `--dry-run` / `--apply`
- Select `GuestMealOrder(status=delivered)` missing ledger row
- Idempotent `recognize_guest_meal_profit`
- Print discrepancy table; never mutate regular rows

## Risks / Trade-offs

- **[Risk] Changing `order_delivery` OneToOne → FK** may break assumptions in admin, serializers, tests. → Mitigation: migration + grep/update `meal_profit_transaction` reverse accessor; keep partial unique for regular; expand tests.
- **[Risk] Semantic change of `total_meals_served`** surprises clients expecting stop counts. → Mitigation: additive stop fields; docs; frontend update in same release window.
- **[Risk] Guest profit formula differs from regular snapshot storage** (computed vs `profit_snapshot`). → Mitigation: document clearly; store all components; reconcilable equation; do not overwrite regular behavior.
- **[Risk] Missing published slot at guest delivery** yields `0.00` costs and high apparent profit. → Mitigation: same as regular missing-snapshot policy; surface in reconcile report; do not invent catalog costs.
- **[Risk] Frontend repo out of OpenSpec apply root** (`allowedEditRoots` is backend). → Mitigation: tasks explicitly cover frontend path; apply workflow may need dual-repo work or documented handoff.
- **[Trade-off] Single ledger vs separate table** — single ledger simplifies analytics filters at the cost of a careful uniqueness migration.

## Migration Plan

1. Ship additive model migration + recognition hook + analytics/dashboard fields + tests.
2. Deploy backend; run dry-run reconcile against local/staging; review discrepancies.
3. Apply reconcile only with approval.
4. Ship frontend additive UI/label updates against new fields.
5. Rollback: recognition is additive; feature flag not required if create path is safe — worst case stop calling guest recognition and hide new fields; existing regular rows untouched.

## Open Questions

- Whether Admin Wallet dashboard endpoints that still sum charged-delivery `profit_snapshot` (older `total_profit` / `month_profit` on Admin Wallet) must also include guest in this change, or only the dedicated Admin Profit (`/api/v1/web/admin-profit/`) surface. Default assumption: **Admin Profit + ops dashboard meals-served + guest-meals summary** are in scope; older Admin Wallet funding dashboard profit fields stay regular-charged-delivery unless implementation shows they power `/admin/profit`.
