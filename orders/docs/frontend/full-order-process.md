# Full Order Process (Frontend)

## Summary

**Purchase path:** subscribe — see [`customer-meal-subscription.md`](customer-meal-subscription.md). `POST /orders/` always returns `409 SUBSCRIBE_REQUIRED`.

Historical orders remain list/detail read-only. Admins mark lunch/dinner deliveries from the today board (order-owned or subscription-owned slots).

Target clients: **customer mobile/web** + **admin web**.

## Auth header

```http
Authorization: Token <token>
```

## Customer integration

### 1. Subscribe (replaces create order)

`POST /api/v1/subscriptions/` with `{ "plan_public_id": "..." }`. Success `201`. Do not send `year`/`month`.

Meal identity is the catalog UUID from `GET /api/v1/subscription-plans/` (same `MealCategory.public_id` as `GET /meals/`).

Meal identity is the catalog UUID from `GET /meals/` / `GET /meals/{public_id}/` (not the integer PK). See [`meal-public-uuid.md`](../../../meals/docs/frontend/meal-public-uuid.md).

```json
{ "meal_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "customer_note": "Ring the bell" }
```

Success `201` (important fields):

```json
{
  "public_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
  "meal_public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "meal_type_snapshot": "monthly",
  "order_status": "confirmed",
  "order_month": "2026-07",
  "expected_deliveries": 62,
  "delivered_count": 0,
  "remaining_count": 62,
  "active_days_this_month": ["2026-07-01", "2026-07-02"],
  "deliveries": [
    { "public_id": "11111111-2222-3333-4444-555555555555", "service_date": "2026-07-01", "meal_period": "lunch", "status": "scheduled" }
  ]
}
```

Order/delivery identity cutover: [`order-public-uuid.md`](order-public-uuid.md).

UI tips:
- Show progress as `delivered_count / expected_deliveries`.
- Daily packages: expect `expected_deliveries === 1`.

### 2. List / my orders / detail / current package

- `GET /orders/` — customer: own orders; **verified admin: all orders** (supports `meal_type`, `activity`, `order_month`, …)
- `GET /orders/my-orders/?meal_type=monthly&order_status=active` — customer alias
- `GET /orders/{id}/`
- `GET /orders/current-package/` → `{ "current_package": {...} | null, "message": "..." }`

Do **not** call mark-delivery from customer apps (`403`). Admin mark-delivery stays on `/api/v1/web/orders/...`.

### 3. Cancel (before start only)

`POST /orders/{id}/cancel/` `{ "note": "Changed mind" }`

## Admin integration

Base: `/api/v1/web/orders/`

### List with filters

```
GET /api/v1/web/orders/?meal_type=daily&activity=active&order_month=2026-07
```

Suggested filter chips: Daily / Weekly / Monthly, Active / Inactive, month picker.

### Detail

`GET /api/v1/web/orders/{id}/` — includes `customer_email`, progress, full `deliveries`.

### Today board

```
GET /orders/today-board/?service_date=2026-07-10&meal_period=lunch
GET /orders/today-board/?service_date=2026-07-10&week_of_month=28
```

(Also available at `/api/v1/web/orders/today-board/`.)

### Mark delivery

```
POST /orders/{order_id}/deliveries/{delivery_id}/mark
{ "status": "delivered" | "skipped", "note": "" }
```

(Also available under `/api/v1/web/orders/...`.)

After mark, refresh order detail. For daily, expect `order_status` → `completed`.

## Edge cases / UI states

| State | UI |
|-------|----|
| Month lock on create | Show existing package CTA (current-package) |
| Unpriced meal | Disable buy until cycle finalized |
| Empty today board | “No deliveries scheduled” |
| Idempotent re-mark | Treat 200 same status as success |
| Conflict 409 | Toast “Already marked” |

## Related backend doc

See `orders/docs/backend/full-order-process.md` for full field meanings and cron sync.
