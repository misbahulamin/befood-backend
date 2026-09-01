## Why

Saving customer delivery preferences (`PUT /user_management/customer/delivery-preferences/`) returns HTTP 500: PostgreSQL `FOR UPDATE cannot be applied to the nullable side of an outer join`. After preference save, `resync_future_scheduled_deliveries` locks future `OrderDelivery` rows with `select_for_update()` while `select_related('order', 'subscription')` and an OR filter on nullable parents produce LEFT OUTER JOINs that Postgres rejects. Preview works; preference and day-override writes that trigger resync fail.

## What Changes

- Fix row-locking in `resync_future_scheduled_deliveries` so PostgreSQL accepts the query (lock only `OrderDelivery`, not nullable outer-joined parents)
- Preserve resync behaviour: future `scheduled` snapshots update; `delivered` / `skipped` / `missed` remain untouched
- Keep preference / day-override API contracts unchanged (same status codes and response shapes once resync succeeds)
- Add/extend automated regression covering preference save (or service resync) with subscription-owned and/or mixed nullable-parent deliveries under Postgres
- No schema or frontend contract changes

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `delivery-address-resolution`: Future scheduled delivery address resync after preference/place changes MUST succeed on PostgreSQL when deliveries have nullable `order` and/or `subscription` parents; row locking MUST remain Postgres-safe
- `meal-delivery-preferences`: Preference and day-override writes that trigger resync MUST complete successfully (not `500`) when the customer has future scheduled deliveries with nullable parents

## Impact

- **Code:** `orders/services/delivery_address.py` (`resync_future_scheduled_deliveries`); callers in `user_management/api/delivery_views.py` unchanged except they stop 500ing
- **API:** `PUT .../customer/delivery-preferences/`, `PUT .../customer/delivery-day-overrides/` — behaviour restored, contract unchanged; preview already works
- **DB:** PostgreSQL `SELECT FOR UPDATE` + nullable FK join constraint (same class of bug fixed earlier for meal-off)
- **Tests:** `user_management/tests/test_delivery_addresses.py` (and/or related order delivery address tests)
- **Frontend:** no change once backend 500 is fixed
