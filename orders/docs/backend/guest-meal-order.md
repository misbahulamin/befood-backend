# Guest Meal Orders (Backend)

Prepaid guest meals for **active subscribers** only. Purchases debit the wallet at create time, enforce a monthly quantity cap (Asia/Dhaka), reuse meal-off cutoff and published slot pricing, and attach to the subscriber’s existing `OrderDelivery` stop for rider/kitchen visibility.

## Quick summary

| Concern | Behavior |
|---------|----------|
| Who | Active subscription via `get_active_subscription` |
| What | Extra meals for a concrete `date` + `meal_period` (`lunch` \| `dinner`) |
| Price | Published slot `final_meal_price_snapshot` + `OrderWalletSettings.guest_meal_box_price` |
| Pay | Wallet debit at create (`PAYMENT`, commission_first) with metadata `purpose=guest_meal` |
| Floor | `recharge_balance - total >= meal_stop_threshold` (inclusive) |
| Quota | `SUM(quantity)` for countable statuses in Asia/Dhaka calendar month of `created_at` |
| Limit default | `guest_meal_monthly_limit = 10`, box default `10.00` |
| Delivery charge | Regular slot still charged on deliver; guest totals never re-debited |

## Settings

Admin: `GET/PATCH /api/v1/web/orders/order-wallet-settings/`

| Field | Default | Notes |
|-------|---------|-------|
| `guest_meal_box_price` | `10.00` | Snapshotted on each guest order |
| `guest_meal_monthly_limit` | `10` | Future eligibility only |

See also [wallet-balance-thresholds.md](./wallet-balance-thresholds.md).

## Customer APIs

Base: `/api/v1/guest-meals/`  
Auth: verified customer JWT/token. Scope is always the authenticated customer.

| Method | Path | Side effects |
|--------|------|----------------|
| `GET` | `/api/v1/guest-meals/usage/` | None |
| `POST` | `/api/v1/guest-meals/preview/` | None (quote only) |
| `POST` | `/api/v1/guest-meals/` | Debit + create |
| `GET` | `/api/v1/guest-meals/` | Paginated list |
| `GET` | `/api/v1/guest-meals/{public_id}/` | Detail |

### Request body (preview / create)

```json
{
  "date": "2026-09-30",
  "meal_period": "lunch",
  "quantity": 2
}
```

Clients MUST NOT send prices, balances, subscription ids, or monthly used counts as authoritative input.

### Optional header (create)

`Idempotency-Key: <client-key>`

- Same key + same payload → replay original guest order (`200`, `idempotent_replay: true`).
- Same key + different payload → `409` with `error_code=IDEMPOTENCY_CONFLICT`.

### Usage response

```json
{
  "calendar_month": "2026-09",
  "monthly_limit": 10,
  "used_quantity": 6,
  "remaining_quantity": 4
}
```

### Pricing

```
unit = base + box
total = unit * quantity
```

Snapshots on `GuestMealOrder`: `base_meal_price`, `box_price`, `unit_price`, `total_amount`.

### Eligibility (create & preview)

1. Active subscription
2. `date >= business_today` (Asia/Dhaka)
3. `meal_period` covered by subscription preference
4. Not past meal-off cutoff (`is_past_meal_cutoff`)
5. Regular meal for that date/period is **not** personal Meal-OFF (`OrderDelivery` `skipped` + `skip_source=customer`). Lunch/dinner are independent. Admin/system skips are **not** `PERSONAL_MEAL_OFF` (create still requires a `scheduled` stop → `DELIVERY_UNAVAILABLE` when the stop is not scheduled).
6. Published slot with non-null final price
7. Quantity ≥ 1 and ≤ per-request max (10); remaining monthly capacity
8. Recharge floor after purchase
9. Wallet not frozen / sufficient spendable funds for debit
10. Resolvable subscription `OrderDelivery` stop (create rejects before debit if missing → `DELIVERY_UNAVAILABLE`; successful creates never persist `delivery=null`)

**Meal-OFF interaction (v1, no cancel/refund):** customer Meal-OFF is blocked while scheduled Guest Meals exist for the same slot (`can_meal_off=false` / Meal-OFF API error). Do not silently cancel or refund Guest Meals.

### Wallet debit vs floor (policy note)

- Floor check uses **`recharge_balance − total >= meal_stop_threshold`** (inclusive pass).
- Debit uses wallet ledger default for `PAYMENT`: **`commission_first`** (commission bucket then recharge).
- These are intentional and unchanged in this revision; floor is recharge-gated even though debit may consume commission first.

### Errors

Domain failures return `{ "detail": "...", "error_code": "..." }` with:

| HTTP | Typical codes |
|------|----------------|
| `422` | `NO_ACTIVE_SUBSCRIPTION`, `UNSUPPORTED_MEAL_PERIOD`, `CUTOFF_PASSED`, `PERSONAL_MEAL_OFF`, `DELIVERY_UNAVAILABLE`, `PRICE_UNAVAILABLE`, `MONTHLY_LIMIT_EXCEEDED`, `MEAL_STOP_FLOOR`, `INSUFFICIENT_FUNDS`, `WALLET_FROZEN`, `INVALID_*` |
| `409` | `IDEMPOTENCY_CONFLICT` |
| `404` | Detail not found for this customer |

## Concurrency & idempotency

`create_guest_meal_order` runs in `transaction.atomic()`:

1. Replay short-circuit on existing guest row for idempotency key
2. `select_for_update` wallet
3. `select_for_update` current-month guest rows
4. Revalidate quote / floor / personal Meal-OFF
5. Resolve + `select_for_update(of=('self',))` delivery; require `scheduled`; reject null delivery before debit
6. `debit_wallet` then persist `GuestMealOrder` linked to locked delivery + txn

Failure of either debit or persist rolls back both. Concurrent creates cannot exceed monthly quota or double-spend without keys. Create always revalidates Meal-OFF under the delivery row lock (do not trust preview).

## Delivery / kitchen / activity

- `GuestMealOrder.delivery` links to the subscription slot (`ensure_subscription_deliveries`); create fails if no stop can be resolved.
- Deliveryman board and admin today-board expose `meal_quantity`, `guest_quantity`, and `total_meal_quantity` (`meal + guest`).
- Rider today-summary keeps stop counts (`total`/`delivered`/`pending`) and adds box metrics (`regular_meal_quantity`, `guest_meal_quantity`, `total_meal_quantity`, `delivered_meal_quantity`, `pending_meal_quantity`).
- `get_demand` adds countable guest units to `expected_meal_count` and `final_cooking_count`.
- `charge_delivered_meal` unchanged; guest prepaid only.
- On parent deliver, scheduled guest rows → `delivered`, and
  `recognize_guest_meal_profit` writes an idempotent ledger row (no second wallet debit).
  See `admin_wallet/docs/backend/admin-profit.md`.
- Admin Customer 360 activity includes `guest_meal_ordered`.
- Legacy rows with `delivery=null` (if any) are not auto-refunded; new creates reject missing stops.

## Key code

| Area | Module |
|------|--------|
| Model | `orders.models.GuestMealOrder`, settings fields on `OrderWalletSettings` |
| Service | `orders.services.guest_meal` |
| API | `orders.api.guest_meal_views` |
| Demand | `orders.services.meal_demand.get_demand` |
| Board | `delivery_zones.services.board` |
| Activity | `user_management.services.admin_customer.build_activity_events` |

## Non-goals (v1)

Cancellation/refund, non-subscriber guest meals, admin-on-behalf create, dedicated push notifications, hardcoded box/meal prices outside settings defaults.
