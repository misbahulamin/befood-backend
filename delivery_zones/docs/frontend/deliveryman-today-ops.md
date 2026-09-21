# Deliveryman today ops (BeFood Express mobile)

Contract for **To Deliver / Delivered** tabs, today KPIs, and package display fields.
Backend only in this change — Flutter wiring is a follow-up.

## Auth

```http
Authorization: Token <deliveryman_token>
```

Requires verified Delivery Man (`IsVerifiedDeliveryman`). All endpoints are scoped to the rider’s assigned zone. Foreign `zone_public_id` / client `service_date` / `meal_period` are ignored; “today” uses meal-off timezone (`Asia/Dhaka` by default).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/user_management/deliveryman/deliveries/today-board/` | Location-grouped list |
| GET | `/user_management/deliveryman/deliveries/today-summary/` | Counts + package breakdown |
| POST | `/user_management/deliveryman/deliveries/{delivery_public_id}/mark/` | Mark delivered (unchanged) |

## To Deliver tab (pending)

```http
GET /user_management/deliveryman/deliveries/today-board/
GET /user_management/deliveryman/deliveries/today-board/?status=scheduled
```

Default (no `status`) returns only `scheduled` stops — same as today’s production app.

## Delivered tab

```http
GET /user_management/deliveryman/deliveries/today-board/?status=delivered
```

Returns only `delivered` stops for the active meal window. Rows are not deleted on mark; they leave the pending board via status filter.

### Legacy combined list

```http
GET /user_management/deliveryman/deliveries/today-board/?include_delivered=true
```

When `status` is omitted, `include_delivered=true` still returns scheduled + delivered (backward compatible). Prefer exclusive `status=` for tabs.

## Customer row fields

| Field | Notes |
|-------|--------|
| `meal_name` | Package snapshot (keep for current app) |
| `package_name` | Same snapshot; prefer this for “Package: …” UI |
| `package_public_id` | Meal category UUID when available; may be null |
| `menu_items_label` | Daily menu ingredients (separate from package) |
| `status` | `scheduled` / `delivered` / … — UI may translate `scheduled` → “নির্ধারিত”; de-emphasize in new UI |
| `meal_period`, `meal_quantity`, address / phone / location | Unchanged |
| `delivered_at` | Present when delivered (logistics `delivered_at` or `marked_at`) |
| `delivered_by_rider_public_id`, `delivered_by_name` | When rider attribution exists |

Do **not** remove `meal_name` or `status` — current mobile DTOs depend on them. Prefer showing `package_name` + `menu_items_label` instead of concatenating into one string forever.

### Example customer row (additive fields)

```json
{
  "delivery_public_id": "...",
  "customer_name": "Rahim",
  "customer_phone": "1713000001",
  "status": "delivered",
  "meal_period": "lunch",
  "meal_name": "Student Package",
  "package_name": "Student Package",
  "package_public_id": "...",
  "menu_items_label": "Beef + dhal",
  "meal_quantity": 1,
  "delivered_at": "2026-09-22T07:42:00+00:00",
  "delivered_by_rider_public_id": "...",
  "delivered_by_name": "Rahim Khan"
}
```

## Today summary (KPIs)

```http
GET /user_management/deliveryman/deliveries/today-summary/
```

Same zone / active meal / low-balance exclusion as the board. Counts are **stop counts** (`OrderDelivery` rows), not meal quantity.

```json
{
  "service_date": "2026-09-22",
  "active_meal_period": "lunch",
  "timezone": "Asia/Dhaka",
  "zone": { "public_id": "...", "name": "Zone 1", "code": "zone-1", "priority": 1 },
  "total": 25,
  "delivered": 17,
  "pending": 8,
  "packages": [
    { "package_public_id": "...", "package_name": "Student Package", "count": 12 },
    { "package_public_id": "...", "package_name": "Regular Package", "count": 8 }
  ]
}
```

Empty zone / no active window → zeros + optional `message` (same pattern as board).

## Suggested mobile flow

1. Login → token  
2. Parallel: `today-summary` + `today-board?status=scheduled`  
3. Tab Delivered → `today-board?status=delivered`  
4. Mark delivered → refresh summary + both boards (or optimistic local move)

## Errors

| Case | Status |
|------|--------|
| Not deliveryman / unverified | 401/403 |
| Mark outside assigned zone | 403 |
| Low-balance blocked mark | 422 `MEAL_SERVICE_BLOCKED_LOW_BALANCE` |
| Duplicate mark (already delivered) | 200 idempotent |
| Terminal conflict (e.g. skipped → delivered) | 409 |

## Out of scope

Flutter UI changes, admin 360 redesign, new delivery status enums.
