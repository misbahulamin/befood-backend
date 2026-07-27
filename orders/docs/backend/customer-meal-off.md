# Customer meal-off

## Quick summary

Customers can **meal-off** a scheduled lunch/dinner delivery before cook-prep deadlines. Meal-off sets the slot to `skipped` with `skip_source=customer` (no meal for that user). **No refund** in v1.

| Period | Default deadline (Asia/Dhaka) |
|--------|-------------------------------|
| Lunch on date D | D−1 at **23:59** |
| Dinner on date D | D at **14:00** |

Admin can change times via meal-off settings.

## Endpoints

| Method | Path | Who |
|--------|------|-----|
| POST | `/orders/{id}/deliveries/{delivery_id}/meal-off` | Verified customer (owner) |
| GET/PATCH | `/api/v1/web/orders/meal-off-settings/` | Verified admin |
| GET/PATCH | `/orders/meal-off-settings/` | Verified admin (shared) |

## Customer meal-off

**Request** (optional body):

```json
{ "note": "Out of town" }
```

**Success 200:**

```json
{
  "id": 12,
  "service_date": "2026-07-24",
  "meal_period": "lunch",
  "status": "skipped",
  "skip_source": "customer",
  "can_meal_off": false,
  "meal_off_deadline_at": "2026-07-23T23:59:00+06:00",
  "note": "Out of town"
}
```

**Errors:** `400` deadline passed / invalid state; `404` not owner or missing delivery; `409` already terminal.

## Delivery fields on order detail

- `can_meal_off` — whether meal-off is allowed now
- `meal_off_deadline_at` — RFC3339 deadline for the slot
- `skip_source` — `customer` \| `admin` \| null

## Admin mark vs customer meal-off

| | Admin `.../mark` | Customer `.../meal-off` |
|--|------------------|-------------------------|
| Deadline | Not enforced | Required |
| Status | `delivered` or `skipped` | `skipped` only |
| `skip_source` | `admin` when skipped | `customer` |

## Settings

```json
{
  "timezone": "Asia/Dhaka",
  "lunch_off_time": "23:59:00",
  "dinner_off_time": "14:00:00",
  "updated_at": "..."
}
```

## How to verify

```bash
python manage.py migrate
python manage.py test orders.tests.test_customer_meal_off orders.tests.test_full_order_process
```

OpenSpec: `openspec/changes/customer-meal-off/`
