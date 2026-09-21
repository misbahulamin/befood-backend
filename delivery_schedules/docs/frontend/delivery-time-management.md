# Delivery Time Management (Frontend)

Admin CRUD and public display for BeFood delivery time windows.

## Auth & base paths

| Client | Base | Auth |
|--------|------|------|
| Admin | `/delivery-schedules/` | `Authorization: Token <adminToken>` + verified admin |
| Public | `/delivery-schedules/public/` | None (use `createPublicApiClient()` — strip Authorization) |

Field names are **snake_case** (`start_time`, `end_time`, `is_active`, `sort_order`, `public_id`).

## Admin UI

Suggested route: `/admin/delivery-times` · sidebar label **Delivery Times** (System or Operations).

### List

`GET /delivery-schedules/?is_active=&search=&page=&page_size=&ordering=`

Paginated (`count` / `results`). Columns: name, start, end, status, sort order, actions.

### Create

`POST /delivery-schedules/`

```json
{
  "name": "Breakfast",
  "start_time": "08:00:00",
  "end_time": "10:00:00",
  "is_active": true,
  "sort_order": 0
}
```

Map HTML `<input type="time">` (`HH:MM`) → API `HH:MM:SS` (append `:00` when seconds omitted).

### Update / deactivate

`PATCH /delivery-schedules/{public_id}/` with any subset of writable fields.

### Delete

`DELETE /delivery-schedules/{public_id}/` → `204`. Confirm via `AdminModal`.

### Errors

Use `getApiErrorMessage` / `getApiFieldErrors`. Typical `400` field keys: `name`, `end_time`.

## Public / customer UI

### Fetch

`GET /delivery-schedules/public/` → array (not paginated).

```json
[
  {
    "public_id": "…",
    "name": "Lunch",
    "start_time": "12:30:00",
    "end_time": "14:30:00",
    "sort_order": 1
  }
]
```

### Integration points

1. **Primary:** Package detail policies — replace static Lunch/Dinner windows in `src/features/monthly-package/data/detailStaticContent.ts` (`detailPolicies`) with API-driven rows.
2. **Optional:** Homepage `TrustStrip` / `ServiceHub` dynamic labels from the same list.

### Display rules

- Preserve API order (`sort_order`).
- Format times for Bangla UI (e.g. `১২:৩০ PM – ২:৩০ PM`); do not hardcode schedule names or windows.
- If empty: omit window rows; keep unrelated policy rows (pause/area).

## Timezone note

Values are Asia/Dhaka wall-clock times. Do not treat `start_time` as a UTC ISO datetime.

## Clone patterns

- Admin CRUD: Ingredients / FAQ types (`AdminModal` + RHF + zod + TanStack Query + `sonner`)
- Public fetch: FAQs public catalog (`createPublicApiClient`)
