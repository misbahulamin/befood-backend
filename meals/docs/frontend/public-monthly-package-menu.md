# Public Monthly Package Menu API (Frontend)

Unauthenticated marketing pages use this endpoint to render the published monthly menu for a meal package (calendar + list views).

**Example pages:** `/monthly-package/Premium-Package`, `/monthly-package/Student-Package`

---

## Endpoint

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/meals/public-package-menu/` | None (`AllowAny`) |

### Query parameters

| Param | Required | Meaning |
|-------|----------|---------|
| `meal_public_id` | Yes | Package UUID from `GET /meals/` or detail |
| `year` | No* | Calendar year |
| `month` | No* | Calendar month `1`–`12` |

\*Omit both for current local month. If one is sent, both are required.

---

## Recommended UI workflow

1. Resolve slug → `meal_public_id` via existing meals list (`useMonthlyPackageBySlug`).
2. Call `GET /meals/public-package-menu/?meal_public_id=…&year=…&month=…`.
3. If `schedule_published === false` but `nearest_published_month` is set → auto-navigate once to that month (marketing page default).
4. If `schedule_published === false` and `nearest_published_month` is `null` → show “Menu not published yet” (no placeholder dishes).
5. If `schedule_published === true` → group flat `days[]` by `service_date` for calendar/list.
6. Use `meta.cycle_days` for “30 Days Menu” / “31 Days Menu” labels.
7. Use `meta.meal_period` to show/hide lunch vs dinner columns (`lunch` | `dinner` | `both`).

---

## Success response (`200`)

```json
{
  "year": 2026,
  "month": 8,
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "meal_name": "Premium Package",
  "schedule_published": false,
  "nearest_published_month": { "year": 2026, "month": 9 },
  "published_months": [{ "year": 2026, "month": 9 }],
  "meta": {
    "cycle_days": 31,
    "total_meals": 62,
    "meal_period": "both",
    "meal_period_display": "Both"
  },
  "days": []
}
```

When the requested month is published, `nearest_published_month` equals the requested month and `days` is populated.

### Discovery fields

| Field | Use in UI |
|-------|-----------|
| `nearest_published_month` | Auto-navigate on first load when current month is unpublished |
| `published_months` | Month picker hints / admin troubleshooting |

### `meta` fields

| Field | Use in UI |
|-------|-----------|
| `cycle_days` | Hero chip + section title (“31 দিনের মেনু”) |
| `total_meals` | Optional stats / billing copy |
| `meal_period` | Filter visible lunch/dinner columns |
| `meal_period_display` | Hero “meal option” chip |

---

## Admin troubleshooting

Publish is scoped to the **cycle month** linked to the schedule (e.g. September 2026). If admin publishes September but visitors default to August (current calendar month), the API correctly returns `schedule_published: false` for August until August is separately published.

**Production check (2026-08-27):** Student Package — August `false`, September `true` with 60 slots.

---

## Errors

| Status | When |
|--------|------|
| `400` | Missing `meal_public_id`, invalid month, or incomplete year/month pair |
| `404` | Unknown or inactive meal |

---

## Related endpoints

| Endpoint | When to use |
|----------|-------------|
| `GET /meals/public-package-menu/` | Marketing `/monthly-package/*` (no login) |
| `GET /meals/order-menu-preview/` | Order flow (verified customer) |
| `GET /meals/my-package-menu/` | Post-subscribe hub (`/account/monthly-menu`) |

All three share the same flat `days[]` slot shape and `meta` block. Only the public endpoint includes `nearest_published_month` and `published_months`.
