# Frontend: admin subscription management

## What changed

Admins manage **subscription plans** (same `MealCategory` rows as kitchen packages) and a **subscriber board**. There is no second plan table. `public_id` is the meal package UUID.

Wallet settings still live on `OrderWalletSettings`: `min_wallet_balance_to_order` is the **minimum balance to subscribe** (check only; no debit at subscribe).

**Target client:** Admin web. Permission: `IsVerifiedAdmin`.

## Auth

```http
Authorization: Token <admin-token>
```

Unauthenticated → `401`. Customer token → `403`.

## Plans

```http
GET    /api/v1/web/subscription-plans/
POST   /api/v1/web/subscription-plans/
GET    /api/v1/web/subscription-plans/{public_id}/
PATCH  /api/v1/web/subscription-plans/{public_id}/
```

`POST`/`PATCH` write `MealCategory`: `meal_name`, `description`, `meal_thumbnail`, `meal_period` (`lunch` | `dinner` | `both`), `is_active`, `is_subscribable`. `total_price` is read-only (cycle finalize). New plans default `is_subscribable=true`.

List query `subscribable_only=true` limits to subscribe catalog rows.

Create uses multipart when uploading a thumbnail (same as other meal uploads).

## Subscribers

```http
GET /api/v1/web/subscriptions/
GET /api/v1/web/subscriptions/{public_id}/
```

Paginated (`page`, `page_size`, max 100). List items: customer email / `customer_public_id`, plan snapshots, `status`, `started_on`, cancel fields, progress (`expected_deliveries`, `delivered_count`, `remaining_count`, `active_days_this_month`).

Filters (unsupported keys or invalid `status` → `400`):

| Query | Meaning |
|-------|---------|
| `status` | `active` \| `cancelled` |
| `plan_public_id` | Meal plan UUID |
| `started_after` / `started_before` | `YYYY-MM-DD` |
| `cancelled_after` / `cancelled_before` | ISO datetime |

Detail includes `deliveries`. Mark delivered stays admin-only:

```http
POST /api/v1/web/subscriptions/{subscription_public_id}/deliveries/{delivery_public_id}/mark
{ "status": "delivered" }
```

Also works on historical order slots via existing `/api/v1/web/orders/{order_id}/deliveries/{id}/mark`. Kitchen demand (`GET` meal-demand) counts **active-subscription** slots (and remaining historical non-cancelled orders). Cancelled subscription **future** slots are excluded.

## Wallet settings (subscribe minimum)

```http
GET|PATCH /api/v1/web/orders/order-wallet-settings/
{ "min_wallet_balance_to_order": "600.00" }
```

Label: “Minimum wallet balance required to subscribe (BDT). Subscribe does not charge the wallet.”

Customers still see the same field on `GET /wallet/`.

## Relationship to old Order UI

Keep historical order list/detail read-only. Do not offer admin “create monthly order for customer.” New service is subscription-owned `OrderDelivery` rows (`order` null, `subscription` set).
