# Delivery Man 360 Analytics (Backend)

## Quick summary

Verified admins can inspect any Delivery Man’s performance (today / month / lifetime), delivery history, activity timeline, meal-window route sequence, and rankings. Rider mark-delivered also persists logistics attribution, optional GPS, activity logs, and daily KPI summaries.

Meal fulfillment status (`scheduled` / `delivered` / `skipped` / `missed`) stays separate from rider **logistics_status**.

| Method | Path | Who | Why |
|--------|------|-----|-----|
| GET | `/api/v1/web/delivery-men/` | Verified admin | List riders + KPI counts |
| GET | `/api/v1/web/delivery-men/{public_id}/` | Verified admin | Lean 360 overview |
| GET | `/api/v1/web/delivery-men/{public_id}/deliveries/` | Verified admin | Paginated history |
| GET | `/api/v1/web/delivery-men/{public_id}/timeline/` | Verified admin | Activity events for a date |
| GET | `/api/v1/web/delivery-men/{public_id}/route/` | Verified admin | Ordered stops for map |
| GET | `/api/v1/web/delivery-men/rankings/` | Verified admin | Compare riders |
| POST | `/user_management/deliveryman/deliveries/{public_id}/mark/` | Verified deliveryman | Meal delivered (+ Phase A logistics) |
| POST | `/user_management/deliveryman/deliveries/{public_id}/logistics/` | Verified deliveryman | Phase B logistics transitions |

Approval / zone-assign remains at `/user_management/admin/deliverymen/`.

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin (`IsVerifiedAdmin`) | All `/api/v1/web/delivery-men/` reads |
| Verified deliveryman | Own-zone mark + logistics |
| Customer / anonymous | `401` / `403` |

## Key models

### `OrderDelivery` (additive logistics fields)

| Field | Meaning |
|-------|---------|
| `delivered_by_rider` | Rider attributed at completion (immutable once set) |
| `logistics_zone` / `logistics_location` | Snapshots at first logistics write |
| `logistics_status` | `assigned` → … → `delivered` / `failed` / `cancelled` |
| `assigned_at` … `failed_at` | Per-status timestamps |
| `completion_latitude` / `completion_longitude` | Optional GPS on complete |
| `delivery_duration_seconds` | pick/start → `delivered_at` |

### `DeliveryActivityLog`

Append-only events: `delivery`, `rider`, `status`, `timestamp`, lat/lng, `source`, `note`.

### `DeliveryManDailySummary`

Unique `(rider, date)` rollup: lunch/dinner/total/completed/failed + average duration.

## Business rules

1. **Meal vs logistics**: skip/miss never increments completed KPIs.
2. **Phase A shortcut**: `POST .../mark/` with `status=delivered` may set logistics `delivered` without accept/pick intermediates.
3. **Phase B**: `POST .../logistics/` enforces allowed transitions; illegal → `409` (`INVALID_TRANSITION`).
4. **Admin mark attribution**: if the actor has no rider profile, attribute to the customer’s zone `assigned_delivery_man` when present.
5. **Date presets** use meal-off business timezone (`Asia/Dhaka` via meal-off settings).
6. Rebuild summaries:  
   `python manage.py rebuild_deliveryman_daily_summaries --from YYYY-MM-DD --to YYYY-MM-DD`

## Resolved open questions

| Question | Decision |
|----------|----------|
| Admin mark attribution | Zone’s assigned rider when admin marks; rider profile when deliveryman marks |
| Failed vs meal status | Logistics `failed` does **not** auto-skip the meal slot |
| Rankings population | Riders with daily summary rows in the period (verified or not) |
| Timezone for “today” | `meal_off_business_now()` (MealOffSettings.timezone) |

## Request / response examples

### Overview

`GET /api/v1/web/delivery-men/{public_id}/`

```json
{
  "public_id": "...",
  "name": "Rahim Khan",
  "phone": "1714000001",
  "assigned_zone": {"public_id": "...", "name": "Zone 02", "code": "zone-02", "priority": 1, "status": "active"},
  "joining_date": "2026-01-15",
  "status": "approved",
  "is_available": true,
  "today": {"total": 57, "lunch": 25, "dinner": 32},
  "month": {"year": 2026, "month": 9, "label": "September 2026", "total": 1240, "lunch": 620, "dinner": 620, "average_per_day": 41.0},
  "lifetime": {"total": 35450, "customers_served": 780, "zones_covered": 5}
}
```

Overview does **not** embed history/timeline arrays.

### Mark delivered (additive GPS)

```json
{ "status": "delivered", "note": "", "latitude": "22.356900", "longitude": "91.783200" }
```

Legacy `{ "status": "delivered" }` still works.

### Logistics transition

```json
{ "status": "picked_up", "latitude": null, "longitude": null }
```

Allowed statuses on this endpoint: `assigned`, `accepted`, `picked_up`, `out_for_delivery`, `failed`, `cancelled` (not meal `delivered` — use mark).

## Errors

| HTTP | When |
|------|------|
| 400 | Unknown filter / missing route params |
| 401 / 403 | Auth / permission |
| 404 | Unknown rider or delivery |
| 409 | Illegal logistics transition |
| 422 | Wallet / meal-service blocked on mark |

## How to verify

```bash
python manage.py migrate orders
python manage.py test user_management.tests.test_admin_deliveryman_360
```

Swagger: `/api/docs/` — tag **Admin Delivery Man 360** / **Delivery Man Board**.
