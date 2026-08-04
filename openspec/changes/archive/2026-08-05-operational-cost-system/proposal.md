## Why

Meal cycle costing still treats “other cost” as a flat percentage of product cost (`other_cost_percent`). Real operations (rent, electricity, salaries, etc.) are absolute monthly expenses that should be allocated per meal from a month’s cost ledger and target meal volume. Without that, finalized package prices cannot reflect true operational overhead, and verified admins cannot see an accurate cost → selling-price preview when planning menus.

## What Changes

- Add a **monthly Operational Cost** ledger: named cost items (rent, electricity, salaries, …) for a given `(year, month)`, with add/edit/delete and a computed monthly total.
- Add a monthly **target meal quantity**; compute and expose **per-meal operational cost** = `total_operational_cost ÷ target_meal_quantity` (decimal money rules).
- **BREAKING** (cycle costing math): replace percentage-based `other_cost = product_cost × other_cost_percent / 100` with absolute allocation:
  - `other_cost` (plan / package) = `expected_servings × per_meal_operational_cost` for that plan’s cycle month
  - Keep `profit = product_cost × profit_percent / 100`
  - `total_cost = product_cost + other_cost + profit`
  - `per_meal_rate = total_cost / expected_servings`
- Deprecate / stop using `MealCyclePlan.other_cost_percent` as the source of other cost (field may remain for migration/compat then be removed or ignored; new summaries MUST NOT compute other cost from that percent).
- Snapshot `other_cost` on finalize continues to lock the allocated operational amount for the plan.
- Add verified-admin APIs for operational cost CRUD, monthly totals, target meals, and per-meal rate; integrate into cycle-plan **summary**, **finalize**, and a **menu-schedule / costing preview** that shows selected ingredients cost, per-meal operational cost, profit percent, and final meal price.
- Costing breakdown fields remain **verified-admin only** (`IsVerifiedAdmin`); public/customer meal APIs MUST NOT expose operational cost ledger, per-meal op cost internals, profit percent, or admin cost previews.
- Backend-only for this change’s implementation tasks; frontend Admin UI is a follow-up after APIs and tests are ready.

## Capabilities

### New Capabilities

- `operational-cost`: Monthly operational cost items, monthly totals, target meal quantity, per-meal operational cost, and verified-admin APIs/permissions for managing and reading them.

### Modified Capabilities

- `meal-cycle-costing`: Other cost becomes meal-count × per-meal operational cost for the cycle month (not a percent of product cost); package rollup, summary, and finalize snapshots use the new formula; admin costing preview contract updated.
- `meal-cycle-planning`: Cycle plan summary/finalize require a resolvable monthly operational cost month (target meals set) for the plan’s `(year, month)`; verified-admin costing visibility clarified; admin meal price preview available while scheduling menus for a plan.

## Impact

- **Models:** New operational cost month + line-item models (and target meal field); `MealCyclePlan` costing fields/snapshots; likely deprecate `other_cost_percent`.
- **Services:** `meals/services/cycle_calculations.py` (`calculate_package_totals`, `build_plan_summary`, `finalize_plan`); new operational-cost service for totals and per-meal rate; menu schedule preview helper.
- **APIs:** New `/meals/` (or `/api/v1/…`) operational-cost endpoints under `IsVerifiedAdmin`; cycle-plan summary/finalize response shape changes for `other_cost`; menu-schedule preview endpoint or enriched assignment response.
- **Permissions:** Reuse `IsVerifiedAdmin` / `is_verified_admin`; public serializers unchanged for cost internals.
- **Tests/docs:** Costing unit tests, API permission tests, finalize snapshot tests; update `meals/docs` cycle costing docs.
- **Clients:** Admin panel (later) must use new ledger + preview APIs; any client still sending `other_cost_percent` as the driver of other cost will break — migrate to monthly operational cost setup.
- **Out of scope this change:** Frontend Admin UI, customer-facing UI, production deployment runbooks beyond backend readiness.
