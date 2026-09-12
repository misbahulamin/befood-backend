# Meal demand forecasting & kitchen planning

## Quick summary

Admin/Kitchen tooling that turns order deliveries + meal-offs into **expected / meal-off / final cooking** counts, optional **ingredient kg** totals from published monthly menus, and **frozen historical snapshots**.

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/orders/meal-statistics/` | Verified admin | Date/period/package demand analytics |
| GET | `/orders/kitchen/today-meal-requirement/` | Verified admin | Cook headcount, package-wise summary, item-wise contributions + kg (aggregate only — no per-customer list) |
| GET | `/orders/kitchen/today-order-details/` | Verified admin | Cooking customer rows for Order Details PDF (name, phone, package, address, today's menu `ingredient_names` / `menu_items_label`) |
| GET | `/orders/meal-history/` | Verified admin | Persisted snapshots (not live recalculation) |
| GET | `/api/v1/web/orders/meal-statistics/` | Verified admin | Same handlers (web-prefixed alias) |
| GET | `/api/v1/web/orders/kitchen/today-meal-requirement/` | Verified admin | Same handlers (web-prefixed alias) |
| GET | `/api/v1/web/orders/kitchen/today-order-details/` | Verified admin | Same handlers (web-prefixed alias) |
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
Live rows   = live (non-cancelled) OrderDelivery for (service_date, meal_period)
Expected    = all live rows (includes low-balance blocked for separate reporting)
Meal off    = skipped AND not meal-stop blocked
Low balance = meal_service_blocked_low_balance=true (any delivery status)
Final cook  = not skipped AND not meal-stop blocked

Cook exclusion uses the block **flag**, not a live `Wallet.balance < meal_stop_threshold`
recompute. After a successful meal charge that drops balance below meal-stop, the flag is
set immediately (post-charge evaluation), so the next Kitchen Today GET drops
`final_cooking_count` without waiting for the 20:00 wallet-threshold cron.

confirmation_status:
  estimated  → business now ≤ meal-off deadline
  confirmed  → business now > meal-off deadline
```

Low-balance meal-stop blocked customers may still have meal-on (`scheduled`) deliveries, but kitchen must not cook for them: they are omitted from live demand counts, ingredient kg, Order Details `customers[]`, and newly written snapshots. They are **not** treated as meal-off.

Deadlines reuse `MealOffSettings` (default Asia/Dhaka):

| Period | Deadline |
|--------|----------|
| Lunch on D | D at `lunch_off_time` (default 00:00) |
| Dinner on D | D at `dinner_off_time` (default 16:00) |

Kitchen default period (no query params): today in meal-off TZ; **lunch** if local time `< dinner_off_time`, else **dinner**.

## Ingredient math

For each package with `final_cooking_count > 0`, load the **published** `MonthlyMenuSlot` for that package + date + period.

- If ingredient has kg pair (`customers_per_kg`): `kg_per_person = 1 / customers_per_kg`, `quantity = kg_per_person × package_final`
- Aggregate same ingredient across packages
- Each ingredient also exposes:
  - `customer_count` — sum of contributing packages’ `final_cooking_count`
  - `package_contributions[]` — `{ package_public_id, package_name, customer_count }` per package that includes the item
- Flat-cost-only ingredients: listed with `quantity_available=false`, `quantity=null`, but still include headcount/contributions
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
      "meal_off_deadline_at": "2026-08-05T16:00:00+06:00",
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

**Query:** optional `service_date`, `meal_period`, `package_public_id` overrides.

When `service_date` and `meal_period` are omitted, the server uses the default kitchen slot (today + lunch/dinner from meal-off clock). `package_public_id` scopes both `packages[]` and ingredient aggregation. Unknown package → `404`.

**Success 200**

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
      "package_public_id": "...",
      "package_name": "Student Package",
      "total_customers": 10,
      "expected_meal_count": 10,
      "meal_off_count": 0,
      "final_cooking_count": 10
    },
    {
      "package_public_id": "...",
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
      "ingredient_public_id": "...",
      "name": "Dal",
      "unit": "kg",
      "quantity": "1.300000",
      "kg_per_person": "0.100000",
      "quantity_available": true,
      "customer_count": 13,
      "package_contributions": [
        {
          "package_public_id": "...",
          "package_name": "Student Package",
          "customer_count": 10
        },
        {
          "package_public_id": "...",
          "package_name": "Regular Package",
          "customer_count": 3
        }
      ]
    }
  ]
}
```

**Printable sheet:** the Admin Kitchen Today UI prints/downloads from this same filtered payload (no separate print API). History snapshots still store the lean ingredient quantity shape without contribution fields.

## Kitchen today order details

**Query:** same optional `service_date`, `meal_period`, `package_public_id` as kitchen today requirement.

Returns cooking customers only (excludes skipped / meal-off). Each row includes identity fields plus today's published slot menu for that customer's package.

**Success 200**

```json
{
  "service_date": "2026-08-05",
  "meal_period": "lunch",
  "count": 1,
  "customers": [
    {
      "name": "Towaha",
      "phone": "+8801894126298",
      "package_name": "Student Package",
      "address": "Chittagong, Chawkbazar",
      "ingredient_names": ["dhal", "mach", "vat"],
      "menu_items_label": "dhal + mach + vat"
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `ingredient_names` | Published slot ingredient display names (slot item order; default alphabetical by name) |
| `menu_items_label` | Same names joined with ` + `; empty string when no published menu / no items |
| `package_name` | Kept for compatibility; Order Details UI should prefer Menu over Package |

Missing published menu does **not** drop the customer — menu fields are empty.

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
| 404 | Unknown `package_public_id` on statistics or kitchen today |

## How to verify

```bash
python manage.py migrate orders
python manage.py test orders.tests.test_meal_demand
```

OpenSpec: `openspec/changes/meal-demand-kitchen-planning/`
