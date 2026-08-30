# Customer meal-off / meal-on

## Quick summary

Customers can **meal-off** a scheduled lunch/dinner delivery before cook-prep deadlines, and **meal-on** (undo) a customer meal-off while still before the **same** deadline. After the deadline, neither Off nor On is allowed; existing status stays unchanged.

| Period | Default deadline (Asia/Dhaka) |
|--------|-------------------------------|
| Lunch on date D | D−1 at **23:59** |
| Dinner on date D | D at **14:00** |

Admin can change times via meal-off settings. Configured times gate **both** meal-off and meal-on.

### Default vs off

| State | Delivery | Wallet |
|-------|----------|--------|
| Never meal-offed (`scheduled`) | Expected; ops may mark `delivered` | Debit only when marked `delivered` |
| Customer meal-off (`skipped`) | No meal expected | No debit while skipped |
| Meal-on (back to `scheduled`) | Expected again | No debit on meal-on; debit only on later `delivered` |

**No refund** on meal-off in v1.

## Endpoints

| Method | Path | Who |
|--------|------|-----|
| POST | `/orders/{public_id}/deliveries/{delivery_public_id}/meal-off` | Verified customer (owner) |
| POST | `/orders/{public_id}/deliveries/{delivery_public_id}/meal-on` | Verified customer (owner) |
| POST | `/api/v1/subscriptions/{public_id}/deliveries/{delivery_public_id}/meal-off` | Verified customer (subscription owner) |
| POST | `/api/v1/subscriptions/{public_id}/deliveries/{delivery_public_id}/meal-on` | Verified customer (subscription owner) |
| GET/PATCH | `/api/v1/web/orders/meal-off-settings/` | Verified admin |
| GET/PATCH | `/orders/meal-off-settings/` | Verified admin (shared) |

Trailing slash optional for meal-off / meal-on POSTs.

Works for both **order-owned** and **subscription-owned** delivery slots (`order` / `subscription` may be null). On PostgreSQL, meal-off/on lock the delivery row only (`SELECT FOR UPDATE OF` the delivery table) so nullable parent outer joins do not raise `FOR UPDATE cannot be applied to the nullable side of an outer join`.

## Customer meal-off

**Request** (optional body):

```json
{ "note": "Out of town" }
```

**Success 200:** delivery with `status: skipped`, `skip_source: customer`, `can_meal_off: false`, `can_meal_on: true` (while before deadline).

**Errors:** `400` deadline passed / invalid state; `404` not owner or missing delivery; `409` already terminal.

## Customer meal-on

Restores a **customer**-skipped slot to `scheduled` before the same deadline. Clears `skip_source` / mark fields. Does **not** debit the wallet.

**Request** (optional body):

```json
{ "note": "Changed plans" }
```

**Success 200:** delivery with `status: scheduled`, `skip_source: null`, `can_meal_off: true` (while before deadline), `can_meal_on: false`.

**Errors:** `400` deadline passed; `404` not owner; `409` not customer-skipped (e.g. admin skip or already scheduled).

### Order reopen

If meal-off completed a daily (or fully terminal) package, meal-on reopens the order:

- `completed` → `confirmed` when no deliveries are `delivered` yet
- `completed` → `active` when at least one delivery is already `delivered`

Internal helper only — not a public reopen API.

## Delivery fields on order detail

- `can_meal_off` — meal-off allowed now (`scheduled` + before deadline)
- `can_meal_on` — meal-on allowed now (customer-skipped + before deadline)
- `meal_off_deadline_at` — RFC3339 deadline for the slot (gates Off and On)
- `skip_source` — `customer` \| `admin` \| null

## Admin mark vs customer meal-off / meal-on

| | Admin `.../mark` | Customer `.../meal-off` | Customer `.../meal-on` |
|--|------------------|-------------------------|------------------------|
| Deadline | Not enforced | Required | Required (same deadline) |
| Status | `delivered` or `skipped` | `skipped` only | `scheduled` only |
| `skip_source` | `admin` when skipped | `customer` | cleared |
| Wallet | Charge on `delivered` | No charge | No charge |

## Settings

```json
{
  "timezone": "Asia/Dhaka",
  "lunch_off_time": "23:59:00",
  "dinner_off_time": "14:00:00",
  "updated_at": "..."
}
```

`lunch_off_time` / `dinner_off_time` apply to both Off and On eligibility checks.

## How to verify

```bash
python manage.py test orders.tests.test_customer_meal_off orders.tests.test_meal_delivery_wallet_payment
```

OpenSpec: `openspec/changes/meal-off-deadline-control/`
