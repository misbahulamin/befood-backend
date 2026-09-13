## 1. Investigate and reuse existing profit logic

- [x] 1.1 Confirm live recognition inputs from `admin_wallet/services/profit.py`, `meals.services.slot_pricing.resolve_published_slot_for_delivery`, and `orders.services.meal_payment` charge metadata
- [x] 1.2 Confirm single delivery success hook points in `orders/services/order_delivery.py` (`mark_delivery` → `charge_delivered_meal`) for both auto cron and manual admin paths
- [x] 1.3 Document current wallet dashboard profit field contract to remove (`total_profit`, `month_profit`, `profit_by_package`) in a short implementation note inside the change folder or code comments only where needed

## 2. Profit ledger model and migration

- [x] 2.1 Add `MealProfitTransaction` (or agreed name) model with public_id, customer, order_delivery (unique/OneToOne), package/meal FK, meal_period, service_date, meal_price, food_cost, optional operational_cost, profit_amount, profit_percentage, source, timestamps
- [x] 2.2 Add DB indexes for analytics filters (`service_date`, package, customer, meal_period) and unique constraint on `order_delivery`
- [x] 2.3 Generate and review Django migration; register model in Django admin (read-only recommended)

## 3. Recognition service and delivery hook

- [x] 3.1 Implement `recognize_meal_profit(delivery, *, source=...)` service that freezes snapshot fields and is idempotent (`get_or_create` / IntegrityError-safe)
- [x] 3.2 Refactor shared snapshot resolution so live calculator and ledger recognition reuse one helper (avoid duplicated formulas)
- [x] 3.3 Hook recognition into successful `charge_delivered_meal` / `mark_delivery` path inside the existing `@transaction.atomic` boundary
- [x] 3.4 Ensure Meal OFF, skip, missed, insufficient/frozen wallet paths create no profit row

## 4. Admin Profit analytics APIs

- [x] 4.1 Add web URLs under `/api/v1/web/admin-profit/` and wire into project web URLConf
- [x] 4.2 Implement `GET .../dashboard/` aggregates from ledger only: lifetime, month, today, package breakdown, meal-period breakdown, daily chart series
- [x] 4.3 Implement `GET .../history/` paginated list with allowlisted filters (`start_date`, `end_date`, package, customer, meal_period`) and `400` on unsupported filters
- [x] 4.4 Support custom date-range / yearly totals via documented dashboard or aggregate query params
- [x] 4.5 Add customer-wise profit totals (history filters + aggregate fields or thin endpoint) per spec
- [x] 4.6 Enforce verified-admin auth/permissions consistent with Admin Wallet
- [x] 4.7 Add OpenAPI helpers/examples for dashboard and history

## 5. Remove profit from Admin Wallet dashboard (BREAKING)

- [x] 5.1 Remove profit computation from `admin_wallet/services/queries.dashboard_payload`
- [x] 5.2 Remove `total_profit`, `month_profit`, `profit_by_package` from serializers and OpenAPI for wallet dashboard
- [x] 5.3 Update Admin Wallet tests that asserted profit fields on wallet dashboard

## 6. Historical backfill command

- [x] 6.1 Add management command `backfill_meal_profit` with idempotent create-missing behavior and chunked processing
- [x] 6.2 Add `--dry-run` mode and optional date bounds
- [x] 6.3 Add validation mode comparing ledger sums vs `meal_profit_recognized` / package breakdown; document `service_date` vs `updated_at` axis differences in command help/output

## 7. Documentation

- [x] 7.1 Add Admin Profit frontend doc (endpoints, fields, charts, filters, auth, migration from wallet profit fields)
- [x] 7.2 Update `admin_wallet/docs/frontend/admin-wallet.md` to remove profit-card instructions and point to Admin Profit docs
- [x] 7.3 Add/update backend technical doc for ledger model, recognition hook, backfill runbook

## 8. Tests

- [x] 8.1 Delivery tests: successful auto/manual charged delivery creates profit; Meal OFF / low-balance blocked / failed charge do not
- [x] 8.2 Idempotency tests: retry/concurrent recognition yields a single profit row
- [x] 8.3 Analytics tests: lifetime, month, today, date range, package-wise, customer-wise, meal-period breakdowns
- [x] 8.4 API auth/permission tests for Admin Profit endpoints; unsupported filter → `400`
- [x] 8.5 Backfill tests: historical charged rows migrate; re-run is idempotent; dry-run writes nothing; validation report path works
- [x] 8.6 Wallet dashboard regression: profit fields absent; cash fields still present
- [x] 8.7 Run targeted test suites and fix failures

## 9. Implementation report checklist

- [x] 9.1 After implementation, produce the deliverables report: changed files, new model/migration, delivery hook location, profit logic location, backfill how-to, new API list, removed wallet fields, test results
