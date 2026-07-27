# Operational Costs — Backend Overview

## Why a separate app?

Kitchen overhead (salary, home rent, utilities, extras) is **business cost data**, not meal package data. The `operational_costs` app owns it so that:

1. **Ownership is clear** — month-scoped entries live only here.
2. **No meal FKs** — models never reference `MealCategory`, `MealCycle`, or `MealCyclePlan` (only integer `year` / `month`).
3. **One-way consumption** — `meals` imports kitchen totals for cycle costing; `operational_costs` never imports meals.

```text
operational_costs  (per-month entries, kitchen total for year/month, CRUD)
        ^
        | kitchen_operational_cost_total(cycle.year, cycle.month)
meals               (allocate by plan servings; snapshot on MealCyclePlan)
```

## Why per-month entries?

Admins need to answer “what did we spend in January 2027?” — salary, rent, utilities for that calendar month. A single global catalog cannot represent month-to-month differences.

Each `OperationalCostEntry` belongs to one `(year, month)` and holds its current `amount`. Duplicate names across months are allowed; uniqueness is `(year, month, slug)`.

## Why no amount history?

Product choice: updating an entry **overwrites** `amount` in place. There is no `effective_from` / `effective_to` versioning and no history API. Simpler UX and less code; prior amounts for that month are not retained for audit.

Deactivate with `is_active=false` to exclude a row from month totals without deleting it.

## Ownership boundary

| Concern | Owner |
|---------|--------|
| `OperationalCostEntry` | `operational_costs` |
| Admin APIs under `/operational-costs/` | `operational_costs` |
| Kitchen `operational_cost_total(year, month)` | `operational_costs.services` |
| Plan allocation by expected servings | `meals.services.operational_cost_allocation` |
| `MealCyclePlan.snapshot_operational_cost` | `meals` (costing snapshot only) |

Catalog services (`operational_costs/services/catalog.py`) MUST NOT import meal models.

## How meals consumes totals

1. Draft plan summary calls `kitchen_operational_cost_total(plan.cycle.year, plan.cycle.month)` and `list_entries(..., active_only=True)`.
2. Meals allocates that month’s total onto the plan via `allocate_operational_cost(plan)`.
3. Finalize stores the allocated amount on `MealCyclePlan.snapshot_operational_cost`.
4. A missing month yields `0.00` (no error). Later entry edits do **not** change finalized snapshots until reopen + re-finalize.

Frontend API guide: [`../frontend/operational-costs.md`](../frontend/operational-costs.md).
