# Package meal period (lunch / dinner / both)

## Quick summary

Admins choose whether a meal package covers **lunch**, **dinner**, or **both**. Expected serving counts for plan finalize, per-meal pricing, and order delivery slots use:

```text
expected_servings = service_days(meal_type, year, month) × periods_per_day(meal_period)
```

| meal_period | periods_per_day |
|-------------|-----------------|
| `lunch` | 1 |
| `dinner` | 1 |
| `both` | 2 |

| meal_type | service_days |
|-----------|--------------|
| `daily` | 1 |
| `weekly` | 7 |
| `half_monthly` | 15 |
| `monthly` | calendar days in month (28–31) |
| `six_months` / `yearly` | inclusive day count from month start (same rules as order duration) |

Examples:

- daily + lunch → **1**
- daily + both → **2**
- monthly + dinner in April → **30**
- monthly + both in January → **62**

## Permissions

| Action | Who |
|--------|-----|
| Create/update meal with `meal_period` | ADMIN / OUTLET_MANAGER |
| Public list/detail (includes `meal_period`) | AllowAny |
| Cycle plan summary / finalize | Verified admin (existing cycle permissions) |

## Key models / fields

- `MealCategory.meal_period` — required; choices `lunch` \| `dinner` \| `both`; DB default `both`
- `Order.meal_period_snapshot` — copied at purchase; drives delivery slot generation
- `MealCycle.total_meals` — remains **calendar capacity** `cycle_days × 2` (not the finalize target for every package)

## Business rules

1. Create/update meal APIs **require** `meal_period`.
2. Plan summary exposes `expected_servings` and `main_servings_expected` from the linked package + cycle year/month.
3. Finalize requires sum of main-role `servings_count` == package `expected_servings`.
4. `per_meal_rate` = `total_cost / expected_servings`.
5. Public fallback `per_meal_price` = `total_price / expected_servings` for present month (when no finalized plan snapshot rate).
6. Delivery slots: one period per service day for lunch/dinner; both periods when `both`.
7. Existing packages migrated to `both`. Existing orders: backfill from package when possible, else daily → `lunch`, multi-day → `both`.

## API examples

### Create meal (multipart)

`POST /api/v1/meals/`

Fields: `meal_name`, `meal_thumbnail`, `meal_type`, **`meal_period`**, `description`, `is_active`

```json
{
  "meal_name": "Student Dinner",
  "meal_type": "monthly",
  "meal_period": "dinner",
  "is_active": true
}
```

### Plan summary (excerpt)

```json
{
  "expected_servings": 30,
  "main_servings_expected": 30,
  "main_servings_total": 30,
  "meal_category": {
    "meal_type": "monthly",
    "meal_period": "dinner"
  },
  "cycle": {
    "year": 2026,
    "month": 4,
    "total_meals": 60
  }
}
```

Note: cycle `total_meals` is still 60 (calendar); package expected servings is 30.

## Errors

| Case | Status |
|------|--------|
| Missing / invalid `meal_period` on create | 400 |
| Finalize main servings ≠ expected | 400 / validation |

## How to verify

```bash
python manage.py migrate
python manage.py test meals.tests.test_serving_counts meals.tests.test_cycle_calculations meals.tests.test_meals orders.tests.test_full_order_process
```

OpenSpec: `openspec/changes/package-meal-period/`
