# Delivery Time Management (Backend)

Informational catalog of delivery time windows (Lunch, Dinner, Breakfast, …) managed by verified admins. **Does not** replace operational `meal_period` (`lunch` / `dinner`) used by orders, kitchen, meal-off, or menu reveal.

## Quick summary

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/delivery-schedules/public/` | None | Active schedules for customers |
| GET | `/delivery-schedules/` | Verified admin | List all (paginated) |
| POST | `/delivery-schedules/` | Verified admin | Create |
| GET | `/delivery-schedules/{public_id}/` | Verified admin | Retrieve |
| PATCH | `/delivery-schedules/{public_id}/` | Verified admin | Partial update |
| DELETE | `/delivery-schedules/{public_id}/` | Verified admin | Hard delete |

Swagger: `/api/docs/` → tags **Public Delivery Schedules** / **Admin Delivery Schedules**.

## Permissions

| Actor | Access |
|-------|--------|
| Anonymous | Public list only |
| Customer | Public list only (admin endpoints → 403) |
| Verified admin (`IsVerifiedAdmin`) | Full CRUD |
| Unverified admin | 403 on admin endpoints |

## Model

`delivery_schedules.DeliverySchedule`

| Field | Type | Notes |
|-------|------|-------|
| `public_id` | UUID | API identity |
| `name` | string (unique) | e.g. Lunch |
| `start_time` | time | Asia/Dhaka wall-clock |
| `end_time` | time | Must be **after** `start_time` (same-day only) |
| `is_active` | bool | Inactive hidden from public list |
| `sort_order` | int | Lower first |
| `created_at` / `updated_at` | datetime | Auto |

Seed migration creates Lunch `12:30–14:30` and Dinner `19:00–21:00` when the table is empty.

## Validation

- `name` required (trimmed); case-insensitive uniqueness
- `start_time` / `end_time` required
- `start_time < end_time` (overnight windows rejected in v1)
- Equal start/end rejected

## Workflows

### Admin creates Breakfast

1. `POST /delivery-schedules/` with Token auth  
2. Body:

```json
{
  "name": "Breakfast",
  "start_time": "08:00:00",
  "end_time": "10:00:00",
  "is_active": true,
  "sort_order": 0
}
```

3. Response `201` with `public_id` and fields.

### Public display

1. `GET /delivery-schedules/public/` (no auth)  
2. Returns only `is_active=true`, ordered by `sort_order`, `name`, `id`.

Example:

```json
[
  {
    "public_id": "…",
    "name": "Lunch",
    "start_time": "12:30:00",
    "end_time": "14:30:00",
    "sort_order": 1
  },
  {
    "public_id": "…",
    "name": "Dinner",
    "start_time": "19:00:00",
    "end_time": "21:00:00",
    "sort_order": 2
  }
]
```

### Deactivate vs delete

- Hide from customers: `PATCH` `{ "is_active": false }`
- Remove permanently: `DELETE` (hard delete, `204`)

## Timezone

`TIME_ZONE = Asia/Dhaka`. Times are daily recurring local wall-clock values stored as `TimeField` — not UTC instants. Clients should display them as local service times without converting as absolute datetimes.

## Non-goals

Does **not** change `MealOffSettings`, `MenuRevealSettings`, or `meal_period` enums.

## How to verify

```bash
python manage.py test delivery_schedules.tests.test_delivery_schedules
```
