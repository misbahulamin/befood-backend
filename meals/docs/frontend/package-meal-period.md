# Frontend: package meal period

## Summary

Meal packages now include **`meal_period`**: `lunch` | `dinner` | `both`. This changes create/update forms, list/detail display, plan-editor expected servings, and order delivery counts.

**Breaking:** create meal must send `meal_period`. Omitting it returns 400.

> **Also breaking (identifiers):** public meal APIs use UUID `public_id` instead of integer `id`. Detail URL is `/meals/<uuid>/`. See [`meal-public-uuid.md`](meal-public-uuid.md).

## Integration steps

1. **Create / edit meal form** — add required control (radio or select): Lunch / Dinner / Both.
2. **Meal list & detail** — show `meal_period` / `meal_period_display` next to meal type.
3. **Plan editor** — use summary fields `expected_servings` and `main_servings_expected` as the main-servings target (do **not** always use `cycle.total_meals`).
4. **Orders / ops boards** — expect fewer slots when period is lunch-only or dinner-only; daily + both yields **2** slots on one day.

## Headers / auth

- Create/update: authenticated manager (`ADMIN` / `OUTLET_MANAGER`), typically `multipart/form-data`
- Public list/detail: no auth required

## Request / response examples

### Create

```http
POST /api/v1/meals/
Content-Type: multipart/form-data
Authorization: Token <token>
```

| Field | Required | Notes |
|-------|----------|--------|
| meal_name | yes | |
| meal_thumbnail | yes (create) | image |
| meal_type | yes | daily, weekly, … |
| meal_period | yes | lunch, dinner, both |
| description | no | |
| is_active | no | default true |

Success `201` includes:

```json
{
  "public_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "meal_name": "Student Dinner",
  "meal_type": "monthly",
  "meal_type_display": "Monthly",
  "meal_period": "dinner",
  "meal_period_display": "Dinner",
  "total_price": null,
  "pricing_status": "unpriced",
  "per_meal_price": null
}
```

### Validation error

```json
{
  "meal_period": ["This field is required."]
}
```

or

```json
{
  "meal_period": ["Invalid meal period. Allowed values: both, dinner, lunch."]
}
```

### Plan summary (admin)

After attaching a package to a cycle, read:

- `expected_servings` — finalize target for main ingredients
- `main_servings_expected` — same value
- `cycle.total_meals` — kitchen calendar capacity (`days × 2`), may differ from package target

UI tip: show “Expected main servings: 30 (dinner × 30 days)” instead of always “60”.

## Edge cases / UI states

| Package | Expected servings (example) |
|---------|-----------------------------|
| Daily lunch | 1 |
| Daily both | 2 |
| Monthly dinner (30-day month) | 30 |
| Monthly both (31-day month) | 62 |

- Changing `meal_period` on a package updates draft plan targets immediately; reopen finalized plans before re-finalizing.
- Order APIs expose `meal_period_snapshot` (purchase-time copy).

## Target clients

- **Web (admin):** meal CRUD + plan editor (required)
- **Mobile / public:** display period label; no create
