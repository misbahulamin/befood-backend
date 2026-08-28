# Instant Meal Offering (Backend)

## 1. Quick summary

Instant Meals are **read-only display cards** projected from **published** monthly menu slots (`MonthlyMenuSlot`). Non-subscribers can browse upcoming cook-day meals. Subscription pricing, publish, and wallet debit are unchanged.

```text
ingredient_cost  = slot.ingredient_cost_snapshot
                   (else live sum of combined unit costs)
operational_cost = resolve_per_meal_operational_cost(service year, month)
profit           = ingredient_cost × InstantMealSettings.profit_percent / 100
price            = ingredient_cost + operational_cost + profit
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET/PATCH | `/meals/instant-meal-settings/` | Admin Instant profit + duration |
| GET | `/meals/instant-meals/` | Public paginated Instant Meal cards |

**Out of scope:** Instant order, payment, delivery.

---

## 2. Permissions

| Caller | Settings | List |
| --- | --- | --- |
| Verified admin | GET/PATCH | GET |
| Customer / public | Denied | GET (`AllowAny`) |
| Unauthenticated | `401`/`403` | GET |

---

## 3. Models / reuse

### `InstantMealSettings` (singleton `pk=1`)

| Field | Meaning |
| --- | --- |
| `profit_percent` | Default `50.00`; applied to Instant ingredient cost only |
| `duration_days` | Allowlist `{1, 3, 7, 15, 25, 30}` (`1` = Today) |
| `updated_at` | Last change |

Load via `InstantMealSettings.load()`. Delete is a no-op.

### Source data (read-only)

- `MonthlyMenuSchedule` with `status=published`
- `MonthlyMenuSlot` + items / ingredients
- `MealCategory` for package name / thumbnail
- Operational cost month via existing `resolve_per_meal_operational_cost`

No Instant Meal persistence table. Card `public_id` is:

```text
{package_public_id}:{YYYY-MM-DD}:{lunch|dinner}
```

---

## 4. Business rules

1. Window: inclusive local dates `[today, today + duration_days - 1]`.
2. Past `service_date` never returned.
3. Draft / unpublished schedules excluded.
4. Lunch and dinner on the same day are separate cards; each package is a separate card.
5. Unpriceable slots (missing op-cost and no usable snapshot / unresolved live costs) are **skipped**, not zeroed.
6. Changing Instant `profit_percent` must **not** rewrite `MealCyclePlan.profit_percent` or slot `final_meal_price_snapshot`.
7. API does **not** return marketing copy; clients use `subscriber_price` for static upsell text.
8. Instant list does **not** apply `MenuRevealSettings` time gates (calendar window only).

---

## 5. Endpoints

### Admin settings

`GET|PATCH /meals/instant-meal-settings/`

```json
{
  "profit_percent": "50.00",
  "duration_days": 7,
  "updated_at": "2026-08-28T12:00:00Z"
}
```

Invalid `duration_days` (e.g. `10`) → `400` with field error.

### Public list

`GET /meals/instant-meals/?page=1&page_size=20`

Pagination: default page size `20`, max `100`.

Ordering: `service_date` ASC → `lunch` before `dinner` → `package_name`.

Example card:

```json
{
  "public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:2026-08-28:lunch",
  "name": "Chicken + Rice + Dal",
  "meal_period": "lunch",
  "meal_type": "lunch",
  "service_date": "2026-08-28",
  "package_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "package_source": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "package_name": "Student Package",
  "price": "70.00",
  "ingredient_cost": "40.00",
  "operational_cost": "10.00",
  "profit_percent": "50.00",
  "image": "http://example.com/media/...",
  "subscriber_price": "54.00",
  "ingredients": [
    {"name": "Chicken", "product_role": "main"},
    {"name": "Rice", "product_role": "staple"},
    {"name": "Dal", "product_role": "side"}
  ]
}
```

---

## 6. Isolation guarantees

| Must not change | Why |
| --- | --- |
| `finalize_plan` / package totals | Subscription package price |
| `publish_schedule` snapshot writes | Subscriber wallet debit source |
| `MealCyclePlan.profit_percent` | Instant uses separate settings |
| Existing public package / today menu APIs | Additive feature only |

Service module: `meals/services/instant_meals.py`.

---

## 7. How to verify

```bash
python manage.py migrate meals
python manage.py test meals.tests.test_instant_meals
python manage.py test meals.tests.test_slot_final_price meals.tests.test_public_package_menu
```

Swagger tags: **Admin Instant Meals**, **Public Instant Meals**.
