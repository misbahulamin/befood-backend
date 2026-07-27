# Frontend: Ops catalog public UUID

## Summary

Admin meal-ops resources now have UUID `public_id` and detail URLs look up by UUID:

- Ingredients: `/meals/ingredients/<uuid>/`
- Cycles: `/meals/cycles/<uuid>/`
- Cycle plans: `/meals/cycle-plans/<uuid>/`
- Plan lines: `/meals/cycle-plan-lines/<uuid>/`
- Menu schedules: `/meals/menu-schedules/<uuid>/`

Responses include both `id` (integer, transitional for write FKs like `plan_id`) and `public_id`. Prefer `public_id` for navigation URLs.

**Write FKs** (e.g. create schedule with `plan_id`) may still accept integer PK in this phase.

## Related

- [`docs/public-uuid-convention.md`](../../../docs/public-uuid-convention.md)
