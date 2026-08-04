# Operational Costs — Legacy Pointer

> **Implemented in `meals`.** The standalone `operational_costs` app was never shipped as code; use meals docs instead.

- Backend: [`../../../meals/docs/backend/operational-costs.md`](../../../meals/docs/backend/operational-costs.md)
- Frontend: [`../../../meals/docs/frontend/operational-costs.md`](../../../meals/docs/frontend/operational-costs.md)

## Contract (meals)

```text
per_meal_operational_cost = sum(items) ÷ target_meal_quantity
other_cost on cycle plan  = expected_servings × per_meal_operational_cost
```

Admin CRUD: `/meals/operational-cost-months/`  
Missing month blocks summary/finalize (validation error, not silent zero).
