## Context

Admin Wallet dashboard (`GET /api/v1/web/admin-wallet/dashboard/`) currently computes realized meal profit on every request via `admin_wallet.services.profit`:

- Scan `OrderDelivery` rows with `payment_status=charged`
- Resolve meal package + published `MonthlyMenuSlot`
- Sum `profit_snapshot` (and revenue from `charged_amount`)

That matches publish-time margin correctly but does not scale, cannot support date-range / customer / meal-period analytics efficiently, and blocks future charts.

Delivery already has a single success path:

```text
run_auto_deliver.sh → auto_deliver_meals → mark_delivery_and_notify
  → mark_delivery (DELIVERED)
  → charge_delivered_meal (wallet debit + payment_status=CHARGED)
```

Manual admin mark-delivered uses the same `mark_delivery` → `charge_delivered_meal` path. Profit recognition must hook there once, not in the cron script alone.

Stakeholders: platform admins (P&L / analytics), Admin Panel frontend, backend orders/wallet teams, ops (backfill once).

Constraints: decimal money (no floats); verified-admin web APIs; reuse slot snapshots; immutable historical rows; idempotent under cron retries.

## Goals / Non-Goals

**Goals:**

- Persist one immutable profit ledger row per successfully charged delivery.
- Create that row in the same successful charge flow as wallet debit (atomic with delivery transaction).
- Serve dashboard/history analytics from the ledger only (no full delivery scan on read).
- Support lifetime, month, today, custom date range, package, customer, meal-period, and daily series aggregates.
- **BREAKING:** remove `total_profit`, `month_profit`, `profit_by_package` from Admin Wallet dashboard.
- One-time idempotent backfill for existing charged deliveries; validate totals vs current live calculator before cutover trust.

**Non-Goals:**

- Changing how menu publish computes `profit_snapshot` / ingredient / operational costs.
- Crediting Admin Wallet cash on meal delivery (unchanged).
- Full P&L (inventory COGS variance, Onahar, referral commissions netting).
- Building Admin Panel UI in this repo (API + docs only).
- Real-time websocket profit pushes.
- Soft-deletes / edits of profit rows after recognition (corrections = separate future process if ever needed).

## Decisions

### 1. Keep profit ledger inside `admin_wallet` app (not a new Django app)

- **Choice:** Model `ProfitTransaction` (or `MealProfitTransaction`) in `admin_wallet`, services under `admin_wallet/services/profit_ledger.py` + analytics queries; web routes under `/api/v1/web/admin-profit/`.
- **Why:** Profit reporting already lives conceptually next to Admin Wallet; reuses app permissions, money helpers, docs layout; avoids Instant App sprawl for one ledger.
- **Alternatives:** New `profit` app — cleaner boundary long-term, more wiring (INSTALLED_APPS, URLs). Revisit if ledger grows beyond meal margin.

### 2. Recognition formula = existing published slot snapshots (frozen at write time)

- **Choice:** On charge success, resolve published slot once and store:
  - `meal_price` = `OrderDelivery.charged_amount` (customer revenue)
  - `food_cost` = `slot.ingredient_cost_snapshot` (null → `0.00` with documented unmatched behavior, matching today’s profit calculator treating missing profit as `0.00`)
  - `operational_cost` = `slot.operational_cost_snapshot` (optional stored field for future COGS clarity; dashboard profit uses margin)
  - `profit_amount` = `slot.profit_snapshot` (null → `0.00`)
  - `profit_percentage` = derived at write: `profit_amount / meal_price * 100` when meal_price > 0, else `0.00` (stored decimal, not recomputed later)
- **Why:** Matches current `admin_wallet.services.profit._profit_for_delivery` semantics and publish-time immutability; later catalog edits cannot rewrite history.
- **Alternatives rejected:** Live recompute at dashboard time; use plan-level averages; infer profit as `meal_price - food_cost` without snapshot (diverges from costing formula that includes operational cost).

### 3. Hook after successful charge attach inside `mark_delivery` transaction

- **Choice:** Call `recognize_meal_profit(delivery)` immediately after `charge_delivered_meal` returns a charged delivery (inside `mark_delivery`’s `@transaction.atomic`). Also call from the already-charged idempotent return paths so retries that re-enter charge still ensure a ledger row exists (create-or-get).
- **Why:** Auto cron and manual mark share one path; wallet debit failure rolls back delivery + profit; charge success without profit is a bug to avoid.
- **Alternatives:** Signal/post_save — harder to test and easy to miss transaction boundaries. Cron-only hook — misses manual deliveries.

### 4. Idempotency via unique `order_delivery` (OneToOne)

- **Choice:** `OrderDelivery` OneToOne (or unique FK) to profit row; `get_or_create` / IntegrityError race handling like meal payment idempotency.
- **Why:** At most one profit event per delivery; cron/admin retries safe.
- **Alternatives:** Separate idempotency string key — redundant if delivery PK is the natural key.

### 5. Period filters use `service_date` for analytics; keep `created_at` for audit

- **Choice:** Dashboard month/today/date-range/daily chart filter primarily on `service_date` (meal served calendar). Store `recognized_at` / `created_at` as write timestamp. Document clearly vs old wallet dashboard which filtered profit by `OrderDelivery.updated_at`.
- **Why:** Product examples are calendar “September profit” and daily graphs by date; `service_date` matches kitchen/ops mental model. Backfill validation can also compare against old `updated_at`-based totals and report delta.
- **Trade-off:** Totals may differ slightly from pre-change wallet dashboard for edge cases where charge day ≠ service day; accept and document; validation command can print both axes.

### 6. New APIs under `/api/v1/web/admin-profit/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/admin-profit/dashboard/` | Lifetime, month, today, package breakdown, meal-period split, daily chart (default current month) |
| GET | `/api/v1/web/admin-profit/history/` | Paginated ledger rows with allowlisted filters: `start_date`, `end_date`, `package`, `customer`, `meal_period` |

Optional later (out of v1 tasks unless cheap): `GET .../by-customer/` — can be derived from history aggregates or a thin dashboard section.

- **Auth:** verified admin only (same pattern as Admin Wallet).
- **Money:** decimal strings in JSON.
- **Dashboard reads:** `Sum`/`Count`/`GroupBy` on ledger table only.

### 7. Strip profit fields from Admin Wallet dashboard

- **Choice:** Remove serializer fields, OpenAPI, and `queries.dashboard_payload` profit computation calls.
- **Why:** Wallet = cash custody; Profit = margin analytics. User-requested **BREAKING** split.
- **Frontend:** Docs state migration: profit cards move to Admin Profit endpoints.

### 8. Historical backfill management command

- **Choice:** `python manage.py backfill_meal_profit` (name finalized in tasks) that iterates charged deliveries missing a profit row, applies same `recognize_meal_profit` helper, is idempotent, supports `--dry-run` and optional date bounds.
- **Validation mode:** Compare ledger `Sum(profit_amount)` vs `meal_profit_recognized()` for overlapping windows; exit non-zero on material mismatch beyond documented tolerance (or print report for ops).
- **Why:** ~12–13 days of history must land before frontend cutover.

### 9. Source field

- **Choice:** Store `source` enum: `auto_delivery` | `manual_delivery` | `backfill` (and optionally infer auto vs manual from `marked_by` / cron actor when available; if ambiguous use `manual_delivery` or `unknown` — prefer `backfill` only for command).
- **Why:** Debugging and audit; analytics can ignore source.

## Risks / Trade-offs

- **[Risk] Totals differ from old `updated_at`-based dashboard after switching to `service_date`** → Mitigation: document in OpenAPI/frontend docs; validation command reports both; optionally expose filter `recognition_axis` later if product demands parity.
- **[Risk] Missing slot snapshot yields 0 profit rows that still create a ledger entry with zeros** → Mitigation: match current behavior; include row so delivery counts stay consistent; log/metric unmatched snapshots.
- **[Risk] Hook failure after charge leaves charged delivery without profit** → Mitigation: recognize inside same atomic block as charge attach; backfill command repairs gaps; alert on charge-without-profit count.
- **[Risk] BREAKING wallet dashboard fields break Admin Panel until frontend updates** → Mitigation: coordinate deploy; frontend docs first; temporary dual-read not desired by product (explicit removal).
- **[Risk] Large backfill locks** → Mitigation: chunked iterator, short transactions per delivery, run off-peak.

## Migration Plan

1. Deploy schema migration (`ProfitTransaction` + indexes + unique delivery).
2. Deploy code with live recognition hook + new APIs; keep wallet profit fields briefly only if coordinated — **preferred:** remove in same release per product request, with frontend switched same day.
3. Run `backfill_meal_profit` on production (dry-run → apply → validate).
4. Smoke Admin Profit dashboard vs known sample totals.
5. Rollback: re-add wallet profit fields from git if needed; ledger table can remain (harmless). Hook can be feature-flagged only if required — default is always-on after deploy.

## Open Questions

- Exact model name: `ProfitTransaction` vs `MealProfitTransaction` — prefer `MealProfitTransaction` to avoid confusion with Admin Wallet / customer wallet transactions; implement as product-facing “profit transaction.”
- Whether to store `operational_cost` on the ledger in v1 (recommended yes for completeness; not required for dashboard profit cards).
- Customer-wise section: include aggregated list on dashboard v1 vs history-only filters first — prefer dashboard summary packages + meal period + daily chart in v1; customer breakdown via history filters / optional aggregate endpoint if time permits in tasks.
