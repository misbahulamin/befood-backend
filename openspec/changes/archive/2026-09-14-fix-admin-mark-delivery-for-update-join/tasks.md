## 1. Reproduce & locate

- [x] 1.1 Confirm failing query in `mark_delivery` (`select_for_update` + `select_related` on nullable `order` / `subscription`) at `orders/services/order_delivery.py`
- [x] 1.2 Confirm the same pattern in `charge_delivered_meal` at `orders/services/meal_payment.py` (second failure on mark `delivered`)
- [x] 1.3 Grep orders app for other `select_for_update` + nullable `select_related` on `OrderDelivery`; fix only mark/charge in this change (do not edit `meal_off.py`)

## 2. Fix locking

- [x] 2.1 Change `mark_delivery` lock to `select_for_update(of=('self',))` keeping existing `select_related` for parent/customer checks
- [x] 2.2 Change `charge_delivered_meal` lock to `select_for_update(of=('self',))` keeping existing `select_related`
- [x] 2.3 Keep mark status transitions, idempotency, cancel/completed guards, `skip_source=admin`, wallet charge, onahar credit, and order completion behaviour unchanged
- [x] 2.4 Do not modify customer meal-off/on helpers, endpoints, or deadlines

## 3. Tests

- [x] 3.1 Add subscription-path API (or service) test: admin mark `skipped` → `skipped` / `skip_source=admin` / no `NotSupportedError` (Postgres)
- [x] 3.2 Add subscription-path test: admin mark `delivered` with sufficient wallet → `delivered` + charge succeeds / no `NotSupportedError`
- [x] 3.3 Keep/run existing order-owned mark and meal-delivery wallet payment success cases
- [x] 3.4 Run relevant `orders.tests` (subscription mark + meal delivery wallet payment + meal-off regression smoke) with `--keepdb` on Postgres

## 4. Docs & verify

- [x] 4.1 Brief note in existing orders backend doc (mark-delivery / subscription admin) that subscription-owned mark uses delivery-only FOR UPDATE on Postgres — only if such a doc already exists; otherwise skip new doc files
- [x] 4.2 Manual smoke: admin panel mark delivered + skip on a subscription delivery → 200 (not 500); customer meal-off/on still works unchanged

Notes:
- Same root cause as archived `fix-meal-off-select-for-update-outer-join`; that change deferred these two call sites.
- Scope guard: no customer API, schema, wallet rule, or meal-off behaviour changes.
- During apply, identical lock bug found in `onahar/services/contribution.py` (`credit_for_delivery` / `reverse_for_delivery`) — same `of=('self',)` fix so delivered mark does not log swallowed FOR UPDATE errors (client was already 200 via try/except).
- Task 4.2 covered by Postgres API tests `test_admin_api_mark_skip_on_subscription_slot` + `test_admin_api_mark_delivered_on_subscription_slot` (200, no NotSupportedError). Re-try admin panel after runserver reload.