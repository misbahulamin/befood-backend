# Frontend Implementation Guide — Dynamic Serving Matrix

Cross-link: OpenSpec change [`dynamic-serving-matrix`](../../../openspec/changes/dynamic-serving-matrix/).

> **Current catalog contract (supersedes role-on-ingredient notes below):**  
> `product_role` lives on **`MealCyclePlanLine`**, not on `Ingredient`.  
> Ingredients use `is_active` + `is_customer_visible` instead.  
> See [`plan-level-ingredient-role-visibility.md`](./plan-level-ingredient-role-visibility.md).

**Public meal list/detail APIs are unchanged** (additive admin-only fields and stricter finalize/schedule validation). Customer-facing meal payloads do not include serving-matrix data.

## 1. Quick summary

Monthly packages (`MealCategory`) share cycle calendars but enforce different serving quotas. Admins configure:

1. **Items per meal** min/max (menu slot item count)
2. **Constraint rows** (role or type × operator × target)
3. **Ingredient taxonomy** (`ingredient_type` on leaf ingredients)

Plan **summary** shows live `constraint_progress` plus operational cost allocation fields. **Finalize** hard-fails if any constraint is unsatisfied. **Menu schedule** writes enforce items-per-meal bounds.

Operational costs (rent / salaries / utilities): see [`operational-costs.md`](operational-costs.md).

| Endpoint | Method | Why |
|----------|--------|-----|
| `/meals/ingredients/` | GET/POST/PATCH | Catalog + `ingredient_type` |
| `/meals/serving-profiles/{meal_public_id}/` | GET/PATCH | Package bounds |
| `/meals/serving-profiles/{meal_public_id}/constraints/` | GET/POST | List/create rules |
| `/meals/serving-constraints/{public_id}/` | GET/PATCH/DELETE | Update/delete rule |
| `/meals/cycle-plans/{public_id}/summary/` | GET | Costing + `constraint_progress` |
| `/meals/cycle-plans/{public_id}/finalize/` | POST | Matrix gate + publish price |
| `/meals/menu-schedules/{public_id}/assignments/` | PUT | Slot writes + item min/max |

Base path follows the existing meals router (same host as other admin meal APIs). Auth: `Authorization: Token <token>` for verified admins (`IsVerifiedAdmin`), same as cycle endpoints.

## 2. Permissions matrix

| Actor | Ingredients | Serving profile/constraints | Cycle plan summary/finalize | Menu assignments |
|-------|-------------|----------------------------|-----------------------------|------------------|
| Verified admin | Full CRUD | Full | Full | Full |
| Customer / anon | Denied | Denied | Denied | Denied |

## 3. Mental model

```text
MealCategory (package)
  └─ PackageServingProfile (items_per_meal_min/max)
       └─ PackageServingConstraint[] (rules)

Ingredient (leaf variation)
  ├─ product_role: main | side | staple | seasoning | other
  └─ ingredient_type: rice | dhal | vegetable | meat | fish | other | null

MealCyclePlan lines → aggregate servings by role and type
  → evaluate each constraint → constraint_progress
```

- **Leaf ingredients remain the plan/menu unit** (e.g. Spinach, Chicken Curry).
- Matrix rules group them by `product_role` and/or `ingredient_type`.
- Exactly **one dimension** per constraint: `product_role` **or** `ingredient_type` (API XOR).
- Default for every package (migration / auto-create): `product_role=main eq expected_servings` — preserves legacy finalize behavior until you add more rules.

## 4. Field dictionary

### Ingredient

| Field | Meaning |
|-------|---------|
| `product_role` | Serving role for role-based constraints |
| `ingredient_type` | Taxonomy for type-based constraints (nullable legacy) |
| pricing fields | Unchanged (`price_per_kg`/`customers_per_kg` or flat `cost_per_customer`) |

### PackageServingProfile

| Field | Meaning |
|-------|---------|
| `meal_public_id` | Package UUID (lookup key) |
| `items_per_meal_min` / `max` | Inclusive bounds; must satisfy `1 ≤ min ≤ max` |
| `constraints` | Nested rule list on profile GET |

### PackageServingConstraint

| Field | Meaning |
|-------|---------|
| `product_role` | Write/read helper — set **xor** with `ingredient_type` |
| `ingredient_type` | Write/read helper — set **xor** with `product_role` |
| `dimension` / `dimension_value` | Stored axis (read-only derived) |
| `operator` | `eq` \| `lte` \| `gte` |
| `target_mode` | `expected_servings` \| `absolute` |
| `absolute_value` | Required when `target_mode=absolute` |
| `target_offset` | Added to expected servings when mode is `expected_servings` |
| `sort_order` | Display order |

### constraint_progress item

| Field | Meaning |
|-------|---------|
| `label` | Human-readable rule |
| `actual` | Aggregated servings |
| `target` | Resolved bound |
| `satisfied` | Boolean |
| `message` | Operator-facing explanation |
| `constraint_id` / `constraint_public_id` | Identifiers |

## 5. Admin workflow (call order)

### A. Create / configure package matrix

1. **Create meal package** — `POST /meals/` (multipart) with `meal_name`, `meal_type`, `meal_period`, thumbnail. No `total_price` (published later by finalize).
2. **GET serving profile** — `GET /meals/serving-profiles/{meal_public_id}/`  
   Auto-creates default main-eq constraint if missing.
3. **PATCH bounds** — e.g. Budget: `{"items_per_meal_min": 1, "items_per_meal_max": 3}`
4. **POST constraints** — e.g. dhal cap:

```json
{
  "ingredient_type": "dhal",
  "operator": "lte",
  "target_mode": "absolute",
  "absolute_value": 40,
  "sort_order": 2
}
```

5. **PATCH/DELETE** individual rules via `/meals/serving-constraints/{public_id}/`.

### B. Ingredients (variations)

1. `POST /meals/ingredients/` with pricing + `product_role` + `ingredient_type`.
2. Filter candidates: `GET /meals/ingredients/?ingredient_type=fish&product_role=main`.

### C. Cycle plan → finalize

1. `POST /meals/cycles/` → year/month.
2. `POST /meals/cycle-plans/` with `cycle` (integer PK) + `meal_public_id` (meal UUID).

3. `PUT /meals/cycle-plans/{id}/lines/` with ingredient servings.
4. `GET .../summary/` — render progress bars from `constraint_progress`.
5. `POST .../finalize/` — succeeds only when every constraint is satisfied; publishes package `total_price`.

### D. Monthly menu schedule

1. Create schedule from finalized plan (existing menu-schedule create).
2. `PUT` assignments — each non-empty slot must have item count in `[min, max]`.
3. Publish when every slot has exactly one main (existing rule) and quotas OK.

## 6. Request / response examples

### PATCH profile

`PATCH /meals/serving-profiles/{meal_public_id}/`

```json
{ "items_per_meal_min": 1, "items_per_meal_max": 3 }
```

### Summary excerpt

```json
{
  "expected_servings": 62,
  "main_servings_total": 50,
  "constraint_progress": [
    {
      "dimension": "product_role",
      "dimension_value": "main",
      "operator": "eq",
      "actual": 50,
      "target": 62,
      "satisfied": false,
      "label": "product_role=main = expected_servings",
      "message": "product_role=main = expected_servings: not satisfied (actual 50, target 62)."
    }
  ]
}
```

### Finalize error (matrix)

```json
{
  "serving_matrix": "One or more package serving constraints are not satisfied.",
  "constraint_progress": [ /* full list */ ],
  "main_servings_total": "Main product servings must equal expected servings (62). Current total is 50."
}
```

`main_servings_total` is included when the classic main-eq rule fails (legacy key for existing UI).

## 7. Error cheat sheet

| Situation | HTTP | Keys to show |
|-----------|------|--------------|
| Inverted min/max | 400 | `items_per_meal_min` / `items_per_meal_max` |
| Both dimensions set | 400 | `product_role` + `ingredient_type` |
| Unknown ingredient_type | 400 | field error |
| Finalize matrix fail | 400 | `serving_matrix`, `constraint_progress` |
| Slot item count out of bounds | 400 | `items_per_meal` |
| Unauthenticated | 401 | — |
| Non-admin | 403 | — |

## 8. UI tips

- Treat draft editing as soft: show unsatisfied rows in summary; only block on finalize.
- Label constraints with `label` or compose from dimension/operator/target.
- When picking daily menu variations, filter ingredients by `ingredient_type` then pick a leaf row.
- Seasoning counts toward items-per-meal by default (any slot item counts).

## 9. How to verify

- Swagger: `/api/docs/` — tag **Admin Meal Cycle** (serving-profiles, serving-constraints, ingredients, cycle-plans).
- Tests: `python manage.py test meals.tests.test_serving_matrix meals.tests.test_cycle_calculations meals.tests.test_meal_cycle_api meals.tests.test_monthly_menu_schedule`
- Optional seed: `python manage.py seed_serving_matrices` (Student/Regular/Premium example matrices).

## 10. Backend note

Evaluation rules: [`../backend/serving-matrix.md`](../backend/serving-matrix.md).
