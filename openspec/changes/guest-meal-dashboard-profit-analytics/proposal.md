# Proposal

## Why

Delivered Guest Meals already sync operational status from the parent `OrderDelivery`, but Admin Dashboard “meals served” and Admin Profit analytics still reflect **regular subscription deliveries only**. Guest boxes are prepaid at purchase and never create `MealProfitTransaction` rows, so realized revenue, food cost, profit, and food-box served totals under-report after delivery. Ops and finance need one consistent source of truth before frontend labels can be trusted.

## What Changes

- Treat **food-box served** metrics separately from **delivery-stop** metrics: `total_meals_served = regular_meals_served + guest_meals_served`, using delivered Guest Meal **quantities** (not order rows) and Asia/Dhaka `service_date`.
- Add **idempotent Guest Meal profit recognition** at parent delivery mark-delivered (status sync path): recognize prepaid guest revenue once, attribute food/ops cost from published slot snapshots × quantity, never re-debit the customer wallet.
- Extend Admin Profit dashboard/history/chart aggregates additively with regular vs guest vs total breakdowns; preserve existing field meanings for current consumers.
- Extend Admin ops dashboard summary additively with regular/guest/total meals-served fields; keep `today_delivery` as delivery-stop count.
- Clarify Admin Guest Meals summary: prepaid order value vs delivered/recognized revenue (and realized guest profit when available).
- Provide a **dry-runable** historical reconciliation path for already-delivered Guest Meals missing ledger rows (no production backfill without explicit approval).
- Update frontend Admin Dashboard, Profit, and Guest Meals pages to consume additive fields and stop conflating prepaid totals with realized revenue.
- **Non-goals / safety:** no double wallet debit; no double revenue recognition; no counting scheduled/cancelled guest boxes as served; no inventing packaging cost from `box_price`; no **BREAKING** renames/removals of existing API fields; no arbitrary rewrites of unrelated subscription, kitchen, or rider flows (additive only).

## Capabilities

### New Capabilities

- `guest-meal-profit-recognition`: Idempotent realization of delivered Guest Meal revenue, attributable cost, and profit into the admin meal-profit reporting system without a second wallet debit.
- `admin-ops-meals-served-reporting`: Admin ops dashboard meals-served KPIs that distinguish regular vs guest food boxes vs delivery stops across lifetime/month/today.
- `admin-guest-meal-financial-summary`: Admin Guest Meals list summary that distinguishes prepaid order value from delivered recognized revenue (and optional realized profit).
- `admin-guest-meal-profit-frontend`: Admin UI contracts for Dashboard, Profit, and Guest Meals pages consuming the additive backend fields without inventing client-side financial formulas.

### Modified Capabilities

- `admin-wallet-meal-profit-reporting`: Lifetime/month/range profit, revenue, food cost, history, and charts MUST include realized Guest Meal contributions while remaining distinguishable from regular subscription meals.
- `admin-wallet-meal-revenue-recognition`: Recognized meal business revenue MUST include delivered Guest Meal prepaid amounts at realization time (not at purchase, and not via Admin Wallet cash credit), without treating scheduled guest prepaid value as delivered revenue.

## Impact

- **Backend (this repo):** `orders/services/guest_meal.py` (delivery sync hook), `orders/services/order_delivery.py` / `meal_payment.py` (no guest re-charge), `admin_wallet/models.py` + migrations (ledger source identity for guest), `admin_wallet/services/profit_ledger.py`, `profit_analytics.py`, `profit` APIs/serializers, `user_management/services/admin_dashboard.py` (+ views/serializers), admin guest-meal summarize API, management command for dry-run reconcile, tests under `admin_wallet/tests/` and `orders/tests/` / `user_management/tests/`, docs under `admin_wallet/docs/` and `orders/docs/`.
- **Frontend (`F:\befood\Software\befood-frontend`):** `AdminDashboardPage`, `AdminProfitPage` (+ history/chart), `AdminGuestMealsPage`, related types/API clients/hooks/tests — additive UI only.
- **Existing systems preserved:** Kitchen demand and rider board already count guest boxes for cooking/delivery; this change aligns **served** and **realized finance** with those quantity definitions after delivery.
- **Data safety:** Historical backfill is opt-in with dry-run; no destructive rewrite of existing regular `MealProfitTransaction` rows.
