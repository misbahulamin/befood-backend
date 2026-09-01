## Why

Admin mark delivery / skip on subscription slots returns HTTP 500: PostgreSQL `FOR UPDATE cannot be applied to the nullable side of an outer join`. Customer meal-off/on already uses `select_for_update(of=('self',))` and works; admin `mark_delivery` (and the nested wallet charge lock) still use plain `select_for_update()` with `select_related` on nullable `order` / `subscription` FKs, so the admin panel path fails while the customer path succeeds.

## What Changes

- Fix row-locking in `mark_delivery` so Postgres accepts the query (lock only the delivery row; keep `select_related` for parent checks)
- Fix the same pattern in `charge_delivered_meal` (called when marking `delivered`) so delivered + wallet charge does not 500 after the first lock is fixed
- Preserve mark rules: status transitions, idempotency, cancel/completed guards, skip_source=admin, wallet debit, onahar credit, order completion side effects
- Add/extend Postgres regression tests for **subscription-owned** admin mark delivered and skipped
- Confirm **order-owned** admin mark still works
- No API contract change (same endpoints, status codes, response shape)
- **No changes** to customer meal-off/on, deadlines, or customer-facing APIs

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `order-delivery-tracking`: Admin mark delivered/skipped MUST succeed for subscription-owned and order-owned delivery slots on PostgreSQL without database locking errors; concurrent marks on the same delivery MUST still serialize on the delivery row
- `meal-delivery-wallet-payment`: Wallet charge lock used when marking delivered MUST succeed for subscription-owned slots on PostgreSQL (same delivery-only FOR UPDATE pattern); charge rules, amounts, and idempotency remain unchanged

## Impact

- **Code:** `orders/services/order_delivery.py` (`mark_delivery`); `orders/services/meal_payment.py` (`charge_delivered_meal`)
- **API:** `POST /api/v1/web/subscriptions/{id}/deliveries/{delivery_id}/mark` (and order-based admin mark if it shares the service) — behaviour restored, contract unchanged
- **DB:** PostgreSQL-specific `SELECT FOR UPDATE` + nullable FK join constraint (same class of bug as `fix-meal-off-select-for-update-outer-join`)
- **Tests:** subscription admin mark + meal delivery wallet payment tests under Postgres
- **Customer flows:** untouched (meal-off/on already fixed; this change must not alter their helpers or rules)
- **Frontend:** no change once backend 500 is fixed
