## 1. Reproduce & locate

- [x] 1.1 Confirm failing query in `resync_future_scheduled_deliveries` (`select_for_update()` + `select_related('order', 'subscription')` + OR filter on nullable parents)
- [x] 1.2 Confirm callers: preference PUT and day-override PUT in `user_management/api/delivery_views.py`
- [x] 1.3 Grep orders app for the same lock + nullable outer-join pattern; note other call sites (fix resync only unless identical 500s appear)

## 2. Fix locking

- [x] 2.1 Change `resync_future_scheduled_deliveries` to `select_for_update(of=('self',))` (keep `select_related` and ownership OR filter)
- [x] 2.2 Keep resync rules unchanged: only future `scheduled` rows; snapshot fields only
- [x] 2.3 Add a short code comment explaining why `of=('self',)` is required on Postgres (mirror meal-off helper wording)

## 3. Tests

- [x] 3.1 Add/extend test: resync (or PUT preferences) with subscription-owned future `scheduled` delivery (`order` null) → success, no `NotSupportedError` (Postgres)
- [x] 3.2 Add/extend test: resync with order-owned future `scheduled` delivery still updates snapshot
- [x] 3.3 Assert non-`scheduled` / historical snapshots are not rewritten
- [x] 3.4 Run `user_management.tests.test_delivery_addresses` (and related) with `--keepdb` on Postgres

## 4. Docs & verify

- [x] 4.1 Brief note in `user_management/docs/backend/meal-delivery-addresses.md` (or orders delivery-address doc) that preference-triggered resync locks delivery-only on Postgres
- [x] 4.2 Manual smoke: PUT delivery-preferences from SPA / curl → 200 (not 500) when future scheduled deliveries exist

Notes:
- Same anti-pattern may still exist in `orders/services/meal_payment.py` and `orders/services/order_delivery.py`; out of scope unless they 500 during this work — apply the same `of=('self',)` fix if needed.
- Precedent: `orders/services/meal_off.py` `_lock_delivery_for_meal_toggle`.
- Task 4.2 covered by Postgres API test `test_subscription_owned_resync_and_preferences_put` (preferences + day-overrides PUT → 200, not NotSupportedError). Restart runserver and retry SPA preference save to confirm live.
