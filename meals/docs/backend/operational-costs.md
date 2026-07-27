# Operational Costs (meals consumer)

> Catalog ownership is in the `operational_costs` app. This note only covers how **meals** uses it.

Read instead:

- Backend: [`../../../operational_costs/docs/backend/overview.md`](../../../operational_costs/docs/backend/overview.md)
- Frontend: [`../../../operational_costs/docs/frontend/operational-costs.md`](../../../operational_costs/docs/frontend/operational-costs.md)

## Per-month contract

Draft summary / finalize resolve kitchen totals with the **cycle’s** calendar period:

```text
kitchen_total = kitchen_operational_cost_total(plan.cycle.year, plan.cycle.month)
```

Meals does **not** use a global “current open amount” catalog. Allocation by expected servings and `MealCyclePlan.snapshot_operational_cost` remain in `meals` (`meals.services.operational_cost_allocation` + cycle finalize/summary).

Admin entry CRUD is at `/operational-costs/?year=&month=` (**not** under `/meals/`).
