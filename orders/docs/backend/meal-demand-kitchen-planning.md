# Meal demand forecasting & kitchen planning

## Quick summary

Admin/Kitchen tooling that turns order deliveries + meal-offs into **expected / meal-off / final cooking** counts, optional **ingredient kg** totals from published monthly menus, and **frozen historical snapshots**.

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/orders/meal-statistics/` | Verified admin | Date/period/package demand analytics |
| GET | `/orders/kitchen/today-meal-requirement/` | Verified admin | Lean today (or override) cook headcount + ingredients |
| GET | `/orders/meal-history/` | Verified admin | Persisted snapshots (not live recalculation) |
| GET | `/api/v1/web/orders/meal-statistics/` | Verified admin | Same handlers (web-prefixed alias) |
| GET | `/api/v1/web/orders/kitchen/today-meal-requirement/` | Verified admin | Same handlers (web-prefixed alias) |
| GET | `/api/v1/web/orders/meal-history/` | Verified admin | Same handlers (web-prefixed alias) |
| — | `python manage.py confirm_meal_demand_snapshots` | Ops | Upsert confirmed snapshots |

Admin SPA uses the shared `/orders/...` base (same as `meal-off-settings`).

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin (`ADMIN` + verified profile / superuser) | All three endpoints + management command |
| Customer | Denied (`401`/`403`) |

## Mental model

```text
Expected   = non-cancelled OrderDelivery rows for (service_date, meal_period)
Meal off   = those with status=skipped
Final cook = Expected − Meal off

confirmation_status:
  estimated  → business now ≤ meal-off deadline
  confirmed  → business now > meal-off deadline
```

Deadlines reuse `MealOffSettings` (default Asia/Dhaka):

| Period | Deadline |
|--------|----------|
| Lunch on D | D−1 at `lunch_off_time` (default 23:59) |
| Dinner on D | D at `dinner_off_time` (default 14:00) |

Kitchen default period (no query params): today in meal-off TZ; **lunch** if local time `< dinner_off_time`, else **dinner**.

## Ingredient math

For each package with `final_cooking_count > 0`, load the **published** `MonthlyMenuSlot` for that package + date + period.

- If ingredient has kg pair (`customers_per_kg`): `kg_per_person = 1 / customers_per_kg`, `quantity = kg_per_person × package_final`
- Aggregate same ingredient across packages
- Flat-cost-only ingredients: listed with `quantity_available=false`, `quantity=null`
- Missing published slot → `ingredients_incomplete=true`

Uses `Decimal` (not float). Quantities serialized as decimal strings.

## Key models / services

- `orders.services.meal_demand` — single calculation path for APIs + snapshot writer
- `MealDemandSnapshot` — unique `(service_date, meal_period, package)`; frozen `ingredient_requirements` JSON

## Admin statistics

**Query**

| Param | Required | Notes |
|-------|----------|-------|
| `service_date` | no | `YYYY-MM-DD`; default today (meal-off TZ) |
| `meal_period` | no | `lunch` \| `dinner`; omit = both blocks |
| `package_public_id` | no | Filter to one meal package |

**Success 200 (shape)**

```json
{
  "service_date": "2026-08-05",
  "periods": [
    {
      "service_date": "2026-08-05",
      "meal_period": "dinner",
      "confirmation_status": "estimated",
      "meal_off_deadline_at": "2026-08-05T14:00:00+06:00",
      "total_customers": 500,
      "expected_meal_count": 500,
      "meal_off_count": 50,
      "final_cooking_count": 450,
      "remaining_meal_count": 450,
      "packages": [
        {
          "package_public_id": "...",
          "package_name": "Premium Package",
          "total_customers": 200,
          "expected_meal_count": 200,
          "meal_off_count": 30,
          "final_cooking_count": 170
        }
      ]
    }
  ]
}
```

## Kitchen today requirement

**Query:** optional `service_date`, `meal_period` overrides.

**Success 200**

```json
{
  "service_date": "2026-08-05",
  "meal_period": "lunch",
  "confirmation_status": "confirmed",
  "expected_meal_count": 500,
  "meal_off_count": 50,
  "final_cooking_count": 450,
  "total_customers": 500,
  "ingredients_incomplete": false,
  "ingredients": [
    {
      "ingredient_public_id": "...",
      "name": "Rice",
      "unit": "kg",
      "quantity": "135.000000",
      "kg_per_person": "0.300000",
      "quantity_available": true
    }
  ]
}
```

## History

**Query:** `service_date` and/or `date_from`/`date_to`, optional `meal_period`, `package_public_id`.

Returns snapshot rows (max 500). After catalog yield edits, stored quantities stay frozen until a new confirm upsert overwrites that key.

## Management command

```bash
python manage.py confirm_meal_demand_snapshots --lookback-days 7
python manage.py confirm_meal_demand_snapshots --now 2026-08-05T16:00:00 --lookback-days 3
```

Only writes when `confirmation_status=confirmed` for the slot. Second run `update_or_create`s (no duplicate keys).

## Errors

| Status | When |
|--------|------|
| 400 | Bad date / meal_period |
| 403 | Non-admin |
| 404 | Unknown `package_public_id` on statistics |

## How to verify

```bash
python manage.py migrate orders
python manage.py test orders.tests.test_meal_demand
```

OpenSpec: `openspec/changes/meal-demand-kitchen-planning/`
