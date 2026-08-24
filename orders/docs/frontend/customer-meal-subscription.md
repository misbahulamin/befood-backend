# Frontend: customer meal subscription

## What changed

Monthly **Order Now** (pick a month, `POST /orders/`) is retired. Bachelor mess customers **subscribe once** to Student / Regular / Premium (or any `is_subscribable` plan) and keep receiving meals until they cancel.

Replace the month picker checkout with: catalog → wallet check → Subscribe → Current → Cancel.

**Target client:** Customer mobile and web.

## Auth / headers

```http
Authorization: Token <customer-token>
Content-Type: application/json
```

Verified customer only. Unauthenticated → `401`. Unverified email → `403`.

## Recommended call order

```text
1. GET /wallet/                          → balance, status, min_wallet_balance_to_order
2. GET /api/v1/subscription-plans/       → catalog (lean)
3. GET /api/v1/subscriptions/current/    → already subscribed?
4. If none and wallet OK → POST /api/v1/subscriptions/  { plan_public_id }
5. Current / home → GET current (or GET /orders/current-package/ during migration)
6. Calendar menu → GET /meals/my-package-menu/?year=&month=
7. Meal-off → POST /api/v1/subscriptions/{id}/deliveries/{delivery_id}/meal-off
8. Cancel → POST /api/v1/subscriptions/current/cancel/
```

Do **not** call `POST /orders/` or `GET /orders/orderable-months/`. If a stale client still does, expect:

```json
{
  "detail": "Monthly meal orders are retired. Subscribe to a meal plan instead.",
  "error_code": "SUBSCRIBE_REQUIRED"
}
```

HTTP `409 Conflict`. Create **no** `Order`. Show Subscribe instead of Order Now.

`GET /orders/current-package/` still works: `current_package` and `current_subscription` are the same active subscription payload, or both `null` with `message: "No active meal subscription."`

## Endpoints

### Catalog

```http
GET /api/v1/subscription-plans/
```

Only `is_active` + `is_subscribable` plans. Fields include `public_id`, `meal_name`, `description`, `meal_thumbnail`, `meal_period`, `total_price`, `per_meal_price`, `pricing_status`.

### Subscribe

```http
POST /api/v1/subscriptions/
Content-Type: application/json

{ "plan_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "customer_note": "" }
```

Success `201`. Snapshots `meal_name_snapshot` / `meal_period_snapshot`, `status: active`, `started_on` (Asia/Dhaka business date). **Does not debit the wallet** and **does not create an Order**.

### Current / detail

```http
GET /api/v1/subscriptions/current/
GET /api/v1/subscriptions/{public_id}/
```

Current: `{ "current_subscription": { ... } | null, "message": "..." }`.

Another customer’s `public_id` → `404`.

Progress fields (read-only): `expected_deliveries`, `delivered_count`, `remaining_count`, `active_days_this_month`. Detail also includes `deliveries` (`can_meal_off`, `can_meal_on`, `meal_off_deadline_at`).

### Cancel

```http
POST /api/v1/subscriptions/current/cancel/
```

Sets `status: cancelled`, `cancel_effective_on` = today. Future `scheduled` slots become `skipped` (`skip_source: system`). **Today’s** slots stay (still follow meal-off). No other customer can cancel this resource via `current/cancel` (they have their own current, or `404`).

## Wallet minimum (subscribe gate)

Reuse `min_wallet_balance_to_order` from `GET /wallet/`. Label it **minimum to subscribe**, not to place a monthly order.

| Condition | UI |
|-----------|-----|
| `status === "frozen"` | Disable Subscribe; wallet frozen copy |
| `balance < min_wallet_balance_to_order` | Prompt recharge; still handle server `400` |
| Exact balance = minimum | Allowed |
| Missing wallet | Treat as `0` |

Subscribe errors (`400` field / `non_field_errors`):

| Signal | Meaning |
|--------|---------|
| `already have an active meal subscription` / `ALREADY_SUBSCRIBED` | Show Current; hide Subscribe |
| `not available to subscribe` / plan not found | Refresh catalog |
| `Insufficient wallet balance` + “subscribe” | Show required vs current; CTA recharge |
| `wallet is frozen` | Support / wait; not recharge-only |

Already-subscribed is rejected **before** the wallet error, so a subscriber with a low balance still sees the subscribed state.

## Screens

- **Subscribe:** plan cards from catalog; disable CTA when frozen or below min; on `201` go to Current.
- **Current:** status, plan name, started_on, progress, delivery list + meal-off.
- **Cancel:** confirm; after success, catalog/Subscribe is available again (v1 has no in-place plan switch — cancel, then subscribe to another plan).
