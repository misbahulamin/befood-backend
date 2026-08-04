# Operational Costs — Frontend Integration

## Base path

All endpoints live under **`/meals/`** (not a separate `/operational-costs/` app).

**Auth:** `Authorization: Token <verified_admin_token>`  
**Permission:** verified admin only. Customers must never call these endpoints.

---

## Endpoints

| Method | Path | When to call |
| --- | --- | --- |
| GET | `/meals/operational-cost-months/?year=&month=` | Month picker / list |
| POST | `/meals/operational-cost-months/` | Create month ledger |
| GET | `/meals/operational-cost-months/{public_id}/` | Detail + computed totals |
| PATCH | `/meals/operational-cost-months/{public_id}/` | Update target / notes |
| DELETE | `/meals/operational-cost-months/{public_id}/` | Delete month |
| PUT | `/meals/operational-cost-months/{public_id}/items/` | Replace all cost lines |
| POST | `/meals/cycle-plans/{public_id}/cost-preview/` | Live one-meal price preview |

---

## Create example

```http
POST /meals/operational-cost-months/
Authorization: Token <admin_token>
Content-Type: application/json

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

Response highlights:

- `total_operational_cost`: `"310000.00"`
- `per_meal_operational_cost`: `"31.00"`

---

## Cost preview example

```http
POST /meals/cycle-plans/{plan_public_id}/cost-preview/
Authorization: Token <admin_token>
Content-Type: application/json

{
  "ingredient_public_ids": ["<uuid>", "<uuid>"]
}
```

Show in admin UI:

- Selected Ingredients Cost
- Per Meal Operational Cost
- Profit Percentage
- Final Meal Price

---

## Breaking change for admin clients

- Do **not** send or display `other_cost_percent` on cycle plans (field removed).
- Before summary/finalize for a month, ensure that month’s operational cost ledger exists with `target_meal_quantity > 0`.
- Public meal APIs still expose only published package / per-meal prices — never op-cost internals.

---

## Suggested Admin UI (follow-up)

Backend is ready; frontend still needs screens for:

1. Operational Cost Management (monthly items + target meals)
2. Per-meal op cost display
3. Cycle plan costing breakdown
4. Menu selection live preview

See backend details: [`../backend/operational-costs.md`](../backend/operational-costs.md).
