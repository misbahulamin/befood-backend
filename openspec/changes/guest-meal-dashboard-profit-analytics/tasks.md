# Tasks

## 1. Ledger model for Guest Meal realization

- [x] 1.1 Extend `MealProfitTransaction` additively (`meal_kind`, `quantity`, nullable unique `guest_meal_order`, relax `order_delivery` OneToOne → FK with partial unique for regular rows, guest source choice) and verify migration applies cleanly on a fresh/local DB
- [x] 1.2 Update admin/serializers/reverse-accessor usages that assumed OneToOne `meal_profit_transaction` and verify existing regular profit tests still pass (`admin_wallet/tests/test_meal_profit.py`)

## 2. Guest Meal profit recognition (backend)

- [x] 2.1 Implement `recognize_guest_meal_profit` using snapshotted `total_amount`, slot `ingredient_cost_snapshot`/`operational_cost_snapshot` × quantity, profit = revenue − costs, and verify Decimal quantization matches regular money helpers
- [x] 2.2 Hook recognition into `sync_guest_meals_for_delivered_delivery` / `mark_delivery` atomic path without a second wallet debit and verify duplicate mark-delivered creates exactly one guest ledger row
- [x] 2.3 Add/extend tests for regular-only, regular+guest qty 2, multiple guest orders per stop, scheduled/cancelled exclusion, concurrent recognition, and purchase-date ≠ service-date; verify suite under `orders/tests/test_guest_meal.py` and `admin_wallet/tests/`
- [x] 2.4 Document recognition rules in `admin_wallet/docs/backend/admin-profit.md` (and guest-meal backend note cross-link) and verify docs match the implemented formula

## 3. Admin Profit analytics API

- [x] 3.1 Extend `profit_analytics.dashboard_payload` / history with additive regular vs guest vs total revenue/cost/profit/meals fields and meal_kind/quantity/guest public id on history rows; verify OpenAPI/serializers and response examples
- [x] 3.2 Ensure date/package/customer/meal_period filters include guest rows by `service_date` and verify filter regression tests pass
- [x] 3.3 Confirm regular-only aggregates remain unchanged for fixtures without guest rows and verify legacy keys still present

## 4. Admin ops dashboard meals served

- [x] 4.1 Update `build_dashboard_summary` to compute regular/guest/total food-box served (guest = Sum delivered quantity) by Asia/Dhaka `service_date`, keep `today_delivery` as stops, add additive stop/box fields as designed; verify API payload in unit/API tests
- [x] 4.2 Update dashboard serializers/docs and verify `total_meals_served` semantic change is documented for clients

## 5. Admin Guest Meals financial summary

- [x] 5.1 Extend `summarize_admin_guest_meals` with prepaid vs delivered recognized revenue (and optional realized profit) while preserving legacy `revenue` prepaid meaning; verify admin guest-meal API tests
- [x] 5.2 Update admin guest-meal frontend/backend docs for unambiguous labels and verify examples match response keys

## 6. Historical reconciliation command

- [x] 6.1 Add management command (dry-run default / explicit apply) to find delivered GuestMealOrders missing ledger rows and idempotently recognize them; verify dry-run writes nothing and apply-twice stays idempotent
- [x] 6.2 Run dry-run against local data for the known 2026-11-16 delivered guest order (qty 2 / ৳140) and capture a reconciliation report artifact before frontend work

## 7. Backend verification gate

- [x] 7.1 Run `python manage.py check` and targeted tests (`admin_wallet`, guest meal, admin dashboard) and verify all pass
- [x] 7.2 Cross-check DB ledger vs Dashboard API vs Profit API vs Guest Meals API for regular/guest/total meals, revenue, cost, profit, and delivery stops; verify equations reconcile before frontend edits

## 8. Frontend Admin Dashboard / Profit / Guest Meals

- [x] 8.1 Update `F:\befood\Software\befood-frontend` Dashboard types/page to show backend total meals served (+ optional regular/guest breakdown) without changing Catalog or stop-card meaning; verify frontend tests
- [x] 8.2 Update Profit page/overview/chart/history to consume guest-inclusive backend aggregates and guest markers; verify tests and no client-side substitute formulas
- [x] 8.3 Update Guest Meals page labels to distinguish prepaid order value vs delivered recognized revenue; verify tests
- [x] 8.4 Run frontend lint/test/build scripts from package.json and verify they pass for touched areas

## 9. End-to-end consistency check

- [x] 9.1 Verify kitchen/rider quantity definitions remain consistent (guest counts for demand/boxes before delivery; served/finance only after delivery) without rewriting those modules unless a real inconsistency is found
- [x] 9.2 Perform browser verification on `/admin/dashboard`, `/admin/profit`, `/admin/guest-meals`, `/admin/kitchen/today` against local APIs and verify DevTools payloads match the reconciliation report

## Workflow follow-up

- After implementation and review, archive this OpenSpec change when the project’s archive workflow is requested.
- Do not run production financial backfill without explicit approval; keep dry-run output for audit.
