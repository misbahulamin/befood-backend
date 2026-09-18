# Zone-based delivery management (frontend)

## Summary

Manual operational routing: **Zone → Location → Customer**, with one primary Delivery Man per zone. Street addresses (`CustomerDeliveryPlace`) stay unchanged. Customer zone is always **derived** from their assigned location—moving a location between zones cascades automatically.

## Auth

All admin endpoints: `Authorization: Token <admin_token>` + verified admin.  
Deliveryman board: verified Delivery Man token.

## Admin — Zones

Base: `/api/v1/web/delivery-zones/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | List zones (`status`, `q`, pagination) |
| POST | `/` | Create zone |
| GET/PATCH/DELETE | `/{public_id}/` | Detail / update / delete if empty |
| PATCH | `/{public_id}/assign-delivery-man/` | Set or clear primary rider (`delivery_man_public_id`) |
| POST | `/{public_id}/deactivate/` | Soft-deactivate |
| GET | `/ops/summary/?service_date=&meal_period=` | Counts + workload |

**Create example**

```json
POST /api/v1/web/delivery-zones/
{
  "name": "Zone 1",
  "code": "zone-1",
  "priority": 1,
  "delivery_man_public_id": null
}
```

## Admin — Locations

Base: `/api/v1/web/delivery-locations/`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | List (`zone_public_id`, `status`, `q`) |
| POST | `/` | Create in a zone |
| GET/PATCH/DELETE | `/{public_id}/` | Detail / update (incl. move zone) / delete if no customers |

**Move location (cascade customers)**

```json
PATCH /api/v1/web/delivery-locations/{public_id}/
{ "zone_public_id": "<zone-2-public-id>" }
```

No per-customer update is required after a move.

## Admin — Customer assignment

```http
PATCH /api/v1/web/customers/{customer_public_id}/delivery-location/
{ "delivery_location_public_id": "<location-public-id>" }
```

Clear: `{ "delivery_location_public_id": null }`

Customer list/detail now include `delivery_location` and derived `delivery_zone`.  
List filters: `zone_public_id`, `location_public_id`, `has_delivery_location`.

## Admin — Deliveryman zone binding

```http
PATCH /user_management/admin/deliverymen/{public_id}/assign-zone/
{ "zone_public_id": "<zone-public-id>" }
```

Clear with `null`. A rider can be primary on only one zone. Only approved/verified riders can be assigned.

Deliveryman list/detail include `assigned_zone`.

## Admin — Today board filters

Existing `/api/v1/web/orders/today-board/` gains optional:

- `zone_public_id`
- `location_public_id`
- `delivery_man_public_id`

## Delivery Man — Today board

```http
GET /user_management/deliveryman/deliveries/today-board/
Authorization: Token <deliveryman_token>
```

**BREAKING:** The board always returns **business today** and the **single active meal period** from meal-off settings (`Asia/Dhaka`). Client `service_date` and `meal_period` query params are **ignored**. Lunch and dinner are never returned together.

Active window (`get_current_delivery_period`):

| Local time | Active period |
|------------|---------------|
| `<= lunch_off_time` | none (empty board; overnight until lunch opens — not prior dinner) |
| after lunch_off through dinner_off | `lunch` |
| after dinner_off | `dinner` |

Optional: `include_delivered=true` to include already delivered rows (default scheduled only).

Foreign `zone_public_id` is ignored—board is always the rider’s assigned zone. No zone → empty periods + message.

**Cooking eligibility (low-balance meal-stop):** The board lists only customers kitchen will cook for. Customers with `meal_service_blocked_low_balance=true` are **omitted** even when lunch/dinner remains on and a `scheduled` delivery row exists. Counts (`total_count`, location `delivery_count`) match that filtered list. Do not expect “every meal-on user in the zone.” Wallet balances are never included on deliveryman payloads.

**Example response shape**

```json
{
  "service_date": "2026-09-18",
  "active_meal_period": "lunch",
  "timezone": "Asia/Dhaka",
  "total_count": 25,
  "zone": { "public_id": "...", "name": "Zone 1", "code": "zone-1", "priority": 1 },
  "periods": {
    "lunch": {
      "total_count": 25,
      "locations": [
        {
          "location_public_id": "...",
          "location_name": "Chawkbazar",
          "location_priority": 1,
          "delivery_count": 10,
          "customers": [
            {
              "delivery_public_id": "...",
              "customer_name": "Rahim",
              "customer_phone": "1713000001",
              "full_address": "...",
              "location_name": "Chawkbazar",
              "location_priority": 1,
              "meal_period": "lunch",
              "meal_name": "Student Package",
              "meal_quantity": 1,
              "notes": "",
              "menu_items_label": "chicken + dhal + vat + vegetable",
              "status": "scheduled"
            }
          ]
        }
      ]
    }
  }
}
```

## Delivery Man — Mark delivered

```http
POST /user_management/deliveryman/deliveries/{delivery_public_id}/mark/
Authorization: Token <deliveryman_token>
Content-Type: application/json

{ "status": "delivered" }
```

- Delivery must belong to the rider’s assigned zone (else 403).
- Reuses the same `mark_delivery` / wallet charge path as admin + cron (`meal-delivery:{public_id}` idempotency).
- **Low-balance meal-stop:** if the customer has `meal_service_blocked_low_balance=true`, mark is rejected with **422** and `error_code: MEAL_SERVICE_BLOCKED_LOW_BALANCE` (same exclusion as auto-delivery cron / kitchen). Status stays unchanged; no wallet debit. Admin mark remains the ops override.
- Already delivered → 200 with same status (no second wallet debit).
- Cron after manual mark skips the slot (no duplicate charge).

**Example response**

```json
{
  "delivery_public_id": "...",
  "status": "delivered",
  "marked_at": "2026-09-18T12:00:00+06:00",
  "payment_status": "charged"
}
```

**Example: meal-stop blocked**

```json
{
  "detail": "Customer meal service is paused due to low wallet balance; delivery cannot be marked by deliveryman.",
  "error_code": "MEAL_SERVICE_BLOCKED_LOW_BALANCE"
}
```

## Cascade rule (UI copy)

> Moving a location to another zone updates every assigned customer’s derived zone immediately. You do not need a bulk customer update.

## Related docs

- Backend: [zone-based-delivery.md](../backend/zone-based-delivery.md)
- Admin customers: [admin-customer-management.md](../../user_management/docs/frontend/admin-customer-management.md)
- Deliveryman auth: [deliveryman-auth.md](../../user_management/docs/frontend/deliveryman-auth.md)
