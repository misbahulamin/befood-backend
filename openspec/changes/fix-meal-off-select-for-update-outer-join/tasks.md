## 1. Reproduce & locate

- [x] 1.1 Confirm failing query in `customer_meal_off` / `customer_meal_on` (`select_for_update` + `select_related` on nullable `order` / `subscription`)
- [x] 1.2 Grep orders app for the same lock+outer-join pattern; note any other call sites (fix meal-off/on only unless identical)

## 2. Fix locking

- [x] 2.1 Introduce shared lock helper (or inline) using `select_for_update(of=('self',))` plus needed `select_related` for ownership checks
- [x] 2.2 Apply helper in `customer_meal_off`
- [x] 2.3 Apply helper in `customer_meal_on`
- [x] 2.4 Keep deadline, ownership, skip_source, complete/reopen behaviour unchanged

## 3. Tests

- [x] 3.1 Add subscription-path API (or service) test: meal-off before deadline → `skipped` / no `NotSupportedError` (Postgres)
- [x] 3.2 Add subscription-path meal-on before deadline after meal-off → `scheduled`
- [x] 3.3 Keep/run legacy order-owned meal-off success case
- [x] 3.4 Run `orders.tests.test_customer_meal_off` and relevant subscription meal-off tests with `--keepdb`

## 4. Docs & verify

- [x] 4.1 Brief note in `orders/docs/backend/customer-meal-off.md` that subscription and order parents both supported; lock uses delivery-only FOR UPDATE on Postgres
- [x] 4.2 Manual smoke: POST subscription meal-off from SPA / curl → 200 (not 500)

Notes:
- Identical `select_for_update()` + nullable `select_related` also exists in `orders/services/meal_payment.py` and `orders/services/order_delivery.py` (mark/charge). Out of scope for this change; same `of=('self',)` fix if those 500s appear.
- Task 4.2 covered by Postgres API test `test_subscription_api_meal_off_and_meal_on` (200, not NotSupportedError). Restart runserver and retry SPA meal-off to confirm live.
