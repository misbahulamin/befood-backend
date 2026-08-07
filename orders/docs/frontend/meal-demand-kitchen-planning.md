# Meal demand & kitchen requirement (Admin / Kitchen UI)

## Summary

Use these web admin APIs to show:

1. **Dashboard metrics** — expected meals, meal-offs, final cooking count, package breakdown, estimated vs confirmed
2. **Kitchen one-click** — today’s cook headcount + ingredient kg list
3. **History** — past confirmed snapshots for analysis

Auth: `Authorization: Token <admin_token>` (verified admin). Prefer `X-Client-Type: web`.

Base: `/orders/` (admin SPA). Same routes also exist under `/api/v1/web/orders/`.

## Integration steps

### A. Admin demand dashboard

1. Load meal-off settings if you show deadlines: `GET .../meal-off-settings/`
2. Call `GET .../meal-statistics/?service_date=YYYY-MM-DD`
3. Optional: `meal_period=lunch|dinner`, `package_public_id=<uuid>`
4. Render each `periods[]` block:
   - Badge **Estimated** vs **Confirmed** from `confirmation_status`
   - Overall: `expected_meal_count`, `meal_off_count`, `final_cooking_count` (same as `remaining_meal_count`)
   - Table from `packages[]`

While `estimated`, copy should say numbers can still change until the meal-off deadline (`meal_off_deadline_at`).

### B. Kitchen “today” screen

1. On open, call `GET .../kitchen/today-meal-requirement/` with **no** query params
2. Morning (before dinner off time, default 14:00 Asia/Dhaka) → lunch; afternoon → dinner
3. Show only:
   - People to cook: `final_cooking_count`
   - Period + date
   - Ingredient list (`quantity` + `unit`); hide or flag rows with `quantity_available=false`
4. If `ingredients_incomplete`, warn that the monthly menu is missing/unpublished for some packages
5. Advanced: pass `service_date` / `meal_period` for planning tomorrow

### C. History / reports

1. `GET .../meal-history/?date_from=...&date_to=...`
2. Bind charts to `final_cooking_count` / `meal_off_count` from the response (frozen data)

Ops should run periodically:

```bash
python manage.py confirm_meal_demand_snapshots
```

## Example responses

See backend doc for full JSON. Kitchen lean shape:

```json
{
  "service_date": "2026-08-05",
  "meal_period": "dinner",
  "confirmation_status": "confirmed",
  "final_cooking_count": 450,
  "ingredients_incomplete": false,
  "ingredients": [
    {
      "name": "Rice",
      "unit": "kg",
      "quantity": "135.000000",
      "quantity_available": true
    }
  ]
}
```

## UI states

| State | UI hint |
|-------|---------|
| `estimated` | Yellow/info — still changing |
| `confirmed` | Green — locked for customer offs |
| `ingredients_incomplete` | Warn kitchen to check menu publish |
| `quantity_available=false` | Show name only (“qty N/A — no kg yield”) |
| Empty demand | Zero cook count is valid |

## Target client

Web admin / kitchen tablet. Not for customer mobile.
