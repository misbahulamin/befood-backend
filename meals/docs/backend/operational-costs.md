# Operational Costs (Backend)

## 1. Quick summary

Verified admins manage a **monthly operational cost ledger** (rent, electricity, salaries, …) plus a **target meal quantity**. The system computes:

```text
total_operational_cost     = sum(item.amount)
per_meal_operational_cost  = total_operational_cost ÷ target_meal_quantity
```

Meal cycle plans then allocate:

```text
other_cost = expected_servings × per_meal_operational_cost
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/meals/operational-cost-months/` | List / create months |
| GET/PATCH/DELETE | `/meals/operational-cost-months/{public_id}/` | Retrieve / update / delete |
| PUT | `/meals/operational-cost-months/{public_id}/items/` | Replace all items |
| POST | `/meals/cycle-plans/{public_id}/cost-preview/` | One-meal admin cost preview |

**Auth:** `Authorization: Token <admin_token>`  
**Permission:** `IsVerifiedAdmin` only  
**Customers / public:** never see ledger, per-meal op cost, or profit breakdown

---

## 2. Permissions

| Caller | Access |
| --- | --- |
| Verified admin / superuser | Full CRUD + cost preview |
| Customer | `403` |
| Unauthenticated | `401` |

---

## 3. Models

### `OperationalCostMonth`

| Field | Meaning |
| --- | --- |
| `public_id` | Opaque UUID for API URLs |
| `year`, `month` | Unique calendar period |
| `target_meal_quantity` | Planned meal volume (> 0) for allocation |
| `notes` | Optional |

### `OperationalCostItem`

| Field | Meaning |
| --- | --- |
| `public_id` | Opaque UUID |
| `month` | FK to `OperationalCostMonth` |
| `name` | e.g. Office Rent |
| `amount` | Absolute BDT amount (Decimal `0.01`) |
| `notes`, `sort_order` | Optional |

---

## 4. Business rules

1. One operational cost month per `(year, month)`.
2. `target_meal_quantity` must be `> 0`.
3. Empty items are allowed → total `0.00` → per-meal `0.00`.
4. Cycle plan **summary** and **finalize** require a resolvable operational cost month for the plan’s cycle year/month. Missing month → validation error (not silent zero).
5. Finalized plan snapshots store absolute `snapshot_other_cost`; later ledger edits do not change finalized figures until reopen + re-finalize.
6. **BREAKING:** `MealCyclePlan.other_cost_percent` is removed. Other cost is no longer a percent of product cost.

---

## 5. Example flows

### Create July ledger

`POST /meals/operational-cost-months/`

```json
{
  "year": 2026,
  "month": 7,
  "target_meal_quantity": 10000,
  "items_payload": [
    {"name": "Office Rent", "amount": "50000.00"},
    {"name": "Electricity", "amount": "10000.00"},
    {"name": "Employee Salary", "amount": "200000.00"},
    {"name": "Chef Salary", "amount": "50000.00"}
  ]
}
```

Response includes:

```json
{
  "total_operational_cost": "310000.00",
  "per_meal_operational_cost": "31.00"
}
```

### Replace items

`PUT /meals/operational-cost-months/{public_id}/items/`

```json
{
  "items": [
    {"name": "Rent Only", "amount": "100000.00"}
  ]
}
```

### Cost preview (one meal)

`POST /meals/cycle-plans/{public_id}/cost-preview/`

```json
{
  "ingredient_public_ids": ["<chicken-uuid>", "<rice-uuid>"]
}
```

Response fields:

- `selected_ingredients_cost` — sum of combined unit costs
- `per_meal_operational_cost`
- `profit_percent`
- `profit`
- `final_meal_price` = ingredients + op cost + profit

---

## 6. Integration with meal cycle costing

See [`meal-cycle-management.md`](./meal-cycle-management.md).

```text
product_cost = sum(line_product_cost)
other_cost   = expected_servings × per_meal_operational_cost
profit       = product_cost × (profit_percent / 100)
total_cost   = product_cost + other_cost + profit
per_meal_rate = total_cost ÷ expected_servings
```

**Workflow order for admins:**

1. Create operational cost month + items + target meals for the calendar month.
2. Create meal cycle + cycle plan + lines.
3. Call summary / cost-preview while editing.
4. Finalize plan (publishes package price).

---

## 7. How to verify

```bash
python manage.py test meals.tests.test_cycle_calculations meals.tests.test_meal_cycle_api
```

Key cases: July `310000 / 10000 = 31`, summary/finalize without month fails, customer denied ledger/preview.

---

## 8. Frontend follow-up (out of scope for this backend change)

Admin UI still needs:

- Monthly ledger CRUD screen
- Target meal quantity input + live per-meal display
- Costing breakdown inside cycle plan / menu schedule flows
- Real-time cost preview when selecting ingredients

Until then, use Swagger / API clients against `/meals/operational-cost-months/` and `cost-preview`.
