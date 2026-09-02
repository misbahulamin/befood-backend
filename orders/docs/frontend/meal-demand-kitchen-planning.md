# Meal demand & kitchen requirement (Admin / Kitchen UI)

## Summary

Use these web admin APIs to show:

1. **Dashboard metrics** — expected meals, meal-offs, final cooking count, package breakdown, estimated vs confirmed
2. **Kitchen Today order summary** — package-wise meal counts, item-wise cooking calculation (headcount + contributions + kg), filters, printable sheet
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

### B. Kitchen Today order summary + print

1. On open, call `GET .../kitchen/today-meal-requirement/` with **no** query params for the server default slot
2. Morning (before dinner off time, default 14:00 Asia/Dhaka) → lunch; afternoon → dinner
3. Render:
   - Hero: `final_cooking_count`, period, date, `confirmation_status`
   - Expected / meal-off line
   - **Package-wise summary** from `packages[]` (customers + final meals; show expected/meal-off on screen)
   - **Item-wise cooking** from `ingredients[]`:
     - `customer_count` (people across packages that include the item)
     - `package_contributions[]` breakdown
     - kg via `quantity` + `unit` when `quantity_available`
4. Filters (Apply / Reset / Refresh):
   - `service_date`, `meal_period`, optional `package_public_id`
   - Package options: reuse packages seen on an unfiltered response (same pattern as Meal Demand), or clear package filter to refresh the list
5. If `ingredients_incomplete`, warn that the monthly menu is missing/unpublished for some packages
6. **Print / Download PDF:** use the **currently loaded** filtered response — do not refetch unfiltered data. Layout:
   - Section 1: package-wise summary
   - Section 2: item-wise calculation
   - Section 3: prep notes (`confirmation_status`, incomplete-menu warning)
   - Prefer browser print (`window.print` / Save as PDF); no separate print API in v1

### C. History / reports

1. `GET .../meal-history/?date_from=...&date_to=...`
2. Bind charts to `final_cooking_count` / `meal_off_count` from the response (frozen data)
3. Snapshot `ingredient_requirements` stay lean (quantity fields only; no contribution breakdown in v1)

Ops should run periodically:

```bash
python manage.py confirm_meal_demand_snapshots
```

## Example kitchen response (dashboard + print contract)

```json
{
  "service_date": "2026-08-05",
  "meal_period": "lunch",
  "confirmation_status": "confirmed",
  "expected_meal_count": 13,
  "meal_off_count": 0,
  "final_cooking_count": 13,
  "total_customers": 13,
  "packages": [
    {
      "package_public_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "package_name": "Student Package",
      "total_customers": 10,
      "expected_meal_count": 10,
      "meal_off_count": 0,
      "final_cooking_count": 10
    },
    {
      "package_public_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      "package_name": "Regular Package",
      "total_customers": 3,
      "expected_meal_count": 3,
      "meal_off_count": 0,
      "final_cooking_count": 3
    }
  ],
  "ingredients_incomplete": false,
  "ingredients": [
    {
      "ingredient_public_id": "11111111-1111-1111-1111-111111111111",
      "name": "Dal",
      "unit": "kg",
      "quantity": "1.300000",
      "kg_per_person": "0.100000",
      "quantity_available": true,
      "customer_count": 13,
      "package_contributions": [
        {
          "package_public_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          "package_name": "Student Package",
          "customer_count": 10
        },
        {
          "package_public_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
          "package_name": "Regular Package",
          "customer_count": 3
        }
      ]
    }
  ]
}
```

## UI states

| State | UI hint |
|-------|---------|
| `estimated` | Yellow/info — still changing |
| `confirmed` | Green — locked for customer offs |
| `ingredients_incomplete` | Warn kitchen to check menu publish (screen + print Section 3) |
| `quantity_available=false` | Still show `customer_count` / contributions; kg as “qty N/A” |
| Empty demand | Zero cook count is valid |
| Unknown package filter | `404` — clear package filter |

## Target client

Web admin / kitchen tablet. Not for customer mobile.
