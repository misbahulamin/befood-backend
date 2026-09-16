## Why

Customer meal-off on subscription deliveries returns HTTP 500: PostgreSQL `FOR UPDATE cannot be applied to the nullable side of an outer join`. After subscription-based meals, `OrderDelivery.order` and `OrderDelivery.subscription` are both nullable; `customer_meal_off` / `customer_meal_on` combine `select_for_update()` with `select_related` on those FKs, which Django turns into LEFT OUTER JOINs that Postgres rejects. Legacy order-only tests may still pass; subscription meal-off (the live frontend path) fails.

## What Changes

- Fix row-locking queries in `customer_meal_off` and `customer_meal_on` so Postgres accepts them (lock the delivery row without FOR UPDATE on nullable outer joins)
- Preserve ownership checks, deadline rules, skip/restore behaviour, and order completion/reopen side effects
- Add/extend automated tests for **subscription-owned** meal-off and meal-on against Postgres (reproduce the outer-join failure mode)
- Confirm legacy **order-owned** meal-off/meal-on still work
- No API contract change (same endpoints, status codes, response shape)

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `customer-meal-off`: Meal-off and meal-on MUST work for both subscription-owned and order-owned delivery slots without database locking errors; concurrent updates MUST still serialize on the delivery row

## Impact

- **Code:** `orders/services/meal_off.py` (primary); possibly small helpers if shared lock pattern is extracted
- **API:** `POST .../subscriptions/{id}/deliveries/{delivery_id}/meal-off` (and meal-on); same for `/orders/...` paths — behaviour restored, contract unchanged
- **DB:** PostgreSQL-specific `SELECT FOR UPDATE` + nullable FK join constraint
- **Tests:** `orders/tests/test_customer_meal_off.py` and/or subscription meal-off tests
- **Frontend:** no change once backend 500 is fixed
