# Operational Costs (meals / frontend pointer)

> Use the standalone app docs for the **BREAKING** per-month API:

- [`../../../operational_costs/docs/frontend/operational-costs.md`](../../../operational_costs/docs/frontend/operational-costs.md)
- Backend overview: [`../../../operational_costs/docs/backend/overview.md`](../../../operational_costs/docs/backend/overview.md)

**BREAKING:** pick `year` + `month`, overwrite amounts on the entry (no history / `.../amount/` endpoints). Base path remains `/operational-costs/`.

Plan summary/finalize operational fields still come from meals cycle-plan endpoints; kitchen totals follow the **cycle’s** year/month.
