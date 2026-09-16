## Why

Admin Wallet dashboard currently recomputes realized meal profit on every request by scanning charged deliveries and joining published slot snapshots. That approach will slow down as delivery volume grows, makes historical/date-range analytics hard, and blocks future graph/forecasting work. Profit should be recognized once at successful charged delivery time and stored as an immutable ledger event that dashboards only read.

## What Changes

- Introduce an immutable meal **profit ledger** (`ProfitTransaction` or equivalent) that records revenue, food cost, profit amount/percentage, package, customer, meal period, service date, and delivery linkage when a meal is successfully delivered and the customer wallet is charged.
- Hook profit recognition into the existing delivery success path (`mark_delivery` → `charge_delivered_meal`) so auto-delivery cron and manual admin mark-delivered share one write path; Meal OFF, low-balance blocked, skipped, and failed deliveries create no profit row.
- Enforce idempotency so duplicate cron/admin retries cannot create duplicate profit for the same delivery.
- Add dedicated Admin Profit APIs for dashboard aggregates (lifetime / month / today, package, meal period, daily chart) and filterable history (date range, package, customer, meal period).
- **BREAKING:** Remove live profit fields from `GET /api/v1/web/admin-wallet/dashboard/` (`total_profit`, `month_profit`, `profit_by_package`) so that endpoint stays wallet cash/custody only.
- Provide a one-time historical backfill from existing charged deliveries (≈12–13 days of production data) using the same recognition rules as live writes, validated against current dashboard totals before cutover.
- Reuse existing slot-snapshot profit/cost resolution (`admin_wallet.services.profit` / `resolve_published_slot_for_delivery`); do not invent a second pricing formula.
- Update Admin Wallet / Profit OpenAPI and frontend docs; add delivery, analytics, and backfill tests.

## Capabilities

### New Capabilities
- `meal-profit-ledger`: Immutable per-delivery profit records created only after successful wallet charge, with idempotent uniqueness and frozen financial snapshots.
- `admin-profit-analytics-api`: Verified-admin web APIs for profit dashboard aggregates and filterable profit history/analytics (package, customer, meal period, date range, daily series).
- `meal-profit-historical-backfill`: One-time (re-runnable/idempotent) backfill of historical charged deliveries into the profit ledger with validation against prior live aggregation.

### Modified Capabilities
- `admin-wallet-admin-api`: Admin Wallet dashboard MUST NOT expose or recompute meal profit summary fields; cash/custody contract remains.
- `admin-wallet-frontend-docs`: Frontend docs MUST point profit cards/graphs to the new Admin Profit endpoints instead of wallet dashboard profit fields.
- `meal-delivery-wallet-payment`: Successful charged delivery MUST also create the corresponding profit ledger entry in the same successful charge flow (or immediately after attach, still inside the delivery transaction boundary).

## Impact

- **Backend apps:** New profit model/services (likely `admin_wallet` or a focused profit module), `orders/services/order_delivery.py` / `meal_payment.py` hook, management command for backfill, serializers/views/urls/OpenAPI under web admin prefix.
- **APIs:** New `GET /api/v1/web/admin-profit/dashboard/` and `GET /api/v1/web/admin-profit/history/` (exact paths finalized in design); **BREAKING** removal of profit fields from Admin Wallet dashboard.
- **Data:** Django migration for profit ledger table + unique constraint on delivery (or equivalent idempotency key); historical backfill command for existing charged rows.
- **Reuse:** `admin_wallet/services/profit.py` recognition logic (`profit_snapshot`, charged deliveries), `meals.services.slot_pricing.resolve_published_slot_for_delivery`, published slot `ingredient_cost_snapshot` / `final_meal_price`.
- **Frontend (out of repo):** Admin Panel must switch profit UI to new APIs; wallet page keeps cash metrics only.
- **Ops:** Run schema migration, then backfill command once on production after deploy; auto-deliver cron unchanged except through shared `mark_delivery` path.
