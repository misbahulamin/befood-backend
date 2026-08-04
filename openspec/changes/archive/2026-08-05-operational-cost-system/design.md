## Context

Cycle plans today compute overhead as `other_cost = product_cost × other_cost_percent / 100` (default 30%) in `meals/services/cycle_calculations.py`, then `profit = product_cost × profit_percent / 100`, and publish totals on finalize. Real BeFood overhead is a monthly ledger of absolute amounts (rent, utilities, salaries) shared across all meals sold that month. `MealCycle` already keys planning by `(year, month)`; operational cost should use the same month key and feed into plan summary/finalize and an admin-only cost preview during menu scheduling.

Stakeholders: verified admins (costing), backend meals module. Public/customer clients must keep seeing only published package/per-meal prices—never ledger or margin internals.

## Goals / Non-Goals

**Goals:**

- Persist per-month operational cost items and a target meal quantity; expose total and per-meal operational cost.
- Change package rollup so `other_cost` is absolute: `expected_servings × per_meal_operational_cost` for the plan’s cycle month.
- Keep profit as a percent of product cost; keep finalize snapshots and publish behavior.
- Verified-admin APIs + permission gating for ledger and cost previews.
- Admin meal-price preview (ingredients + per-meal op cost + profit % + final) usable from cycle-plan / menu-schedule admin flows.

**Non-Goals:**

- Frontend Admin UI (follow-up after backend).
- Changing public meal offering payloads to expose operational/profit breakdown.
- Multi-branch or multi-company operational cost scopes (single global month ledger for now).
- Changing how `expected_servings` / meal-period sizing is derived.
- Replacing profit percent with an absolute profit ledger in this change.

## Decisions

### 1. Data model: month header + line items

**Choice:** `OperationalCostMonth` unique on `(year, month)` with `target_meal_quantity` and `public_id`; child `OperationalCostItem` rows (`name`, `amount`, optional `notes`, `sort_order` / timestamps).

**Rationale:** Matches `MealCycle` month scoping; items stay flexible (Office Rent, Electricity, …) without hard-coding categories; one target meal volume per month for a single shared per-meal rate.

**Alternatives considered:**

- Categories enum only → too rigid for “অন্যান্য” costs.
- Per-package operational cost → contradicts “month total ÷ month target meals” shared allocation.
- Store only per-meal rate without items → loses auditability of the ledger.

### 2. Per-meal formula and precision

**Choice:**

```text
total_operational_cost = sum(item.amount)
per_meal_operational_cost = total_operational_cost / target_meal_quantity
```

Use existing `Decimal` + `ROUND_HALF_UP`; money amounts quantize to `0.01`; per-meal op cost MAY keep finer intermediate precision (align with `COST_PLACES` or money `0.01` consistently in one place—prefer money `0.01` for admin-facing per-meal op cost to match BDT display).

**Rationale:** Matches the product formula; avoids float money.

### 3. When month / target is missing

**Choice:** Summary and finalize MUST require an `OperationalCostMonth` for the plan’s `(year, month)` with `target_meal_quantity > 0`. Zero items are allowed (`total = 0` → per-meal `0`). Missing month or target ≤ 0 → `422` validation error identifying year/month.

**Rationale:** Forces admins to set target meals before locking prices; avoids silent fake overhead; empty ledger is an explicit “no op cost this month.”

**Alternatives:** Default per-meal to `0` without a month record → hides misconfiguration.

### 4. Replace percent-based other cost

**Choice:** Update `calculate_package_totals` to take `per_meal_operational_cost` and `expected_servings`:

```text
other_cost = expected_servings × per_meal_operational_cost
profit = product_cost × profit_percent / 100
total_cost = product_cost + other_cost + profit
per_meal_rate = total_cost / expected_servings
```

Stop using `other_cost_percent` in calculations. Keep the DB field temporarily (nullable / unused) or remove in the same migrations after serializers drop it—prefer remove write path immediately and delete field in migration if no production dependency on the percent value; if historical plans relied on it, migration note: reopen + re-finalize after operational month setup.

**Rationale:** Matches requested Meal Price stack; percent of product cost is the wrong model for fixed monthly overhead.

### 5. Snapshot behavior

**Choice:** Continue storing `snapshot_other_cost` (absolute allocated amount for that plan), not the per-meal rate alone. Optionally also snapshot `per_meal_operational_cost` used at finalize for audit (new nullable field) if useful; not required if `other_cost / expected_servings` recovers it.

**Rationale:** Existing finalize/publish pipeline already depends on snapshot money fields; keep reopen → live recalculation from current ledger + ingredients.

### 6. API shape

**Choice:** Web/admin under existing meals routes, `IsVerifiedAdmin`:

- `GET/POST /meals/operational-cost-months/`
- `GET/PATCH/DELETE /meals/operational-cost-months/{public_id}/`
- Nested or sibling item CRUD; prefer `PUT .../items/` replace-all (same pattern as cycle-plan lines) plus optional item-level CRUD if needed.
- Month detail/list responses include: items, `total_operational_cost`, `target_meal_quantity`, `per_meal_operational_cost`.
- Cycle plan `summary` / `finalize` responses include the new `other_cost` meaning and expose `per_meal_operational_cost` for admin transparency.
- Cost preview: `GET` or `POST` on cycle plan or menu schedule, e.g. `POST /meals/cycle-plans/{public_id}/cost-preview/` with optional ingredient/slot context, returning selected ingredients cost, per-meal op cost, profit percent, final meal price—admin only.

**Rationale:** Matches existing meals ViewSet + `public_id` conventions; keeps costing off public meal serializers.

### 7. Menu schedule preview vs plan summary

**Choice:** Implement preview as a verified-admin action on the cycle plan (and/or schedule that resolves its plan). For “ingredient select” UX, accept proposed ingredient set / current slot selection and return:

- `selected_ingredients_cost` (sum of resolvable unit costs for the selection, or line-based product contribution as defined in specs)
- `per_meal_operational_cost`
- `profit_percent`
- `final_meal_price` / breakdown consistent with package formula scaled to one meal where appropriate

Clarify in specs: preview for a **single meal serving** uses one meal’s product cost from selected ingredients’ per-customer costs + one × per-meal op cost + profit share; package-level summary remains the plan rollup.

**Rationale:** Admin needs live feedback while assigning menus without finalizing; plan summary remains the package-level truth.

### 8. Permissions

**Choice:** All operational cost and cost-preview endpoints use `IsVerifiedAdmin` only. Public meal, order, and customer menu APIs MUST NOT gain these fields.

**Rationale:** Explicit product requirement; matches cycle-plan admin gate.

## Risks / Trade-offs

- [Breaking other_cost math] → Document in proposal; update tests; admins must create operational months before finalize; migrate away from `other_cost_percent`.
- [Shared month target across packages] → If two packages sell overlapping meals, allocation is still “company target meals,” not per-package capacity—document as intentional; revisit multi-scope later.
- [Ledger edits after some plans finalized] → Draft plans recalculate live; finalized snapshots stay until reopen—same as ingredient price edits today.
- [Division by large target vs small actual sales] → Per-meal op cost is planning-time allocation, not actuals vs sales variance accounting—out of scope.
- [Frontend lag] → APIs ship first; admin UI follow-up may temporarily use Swagger/manual calls.

## Migration Plan

1. Add models + migrations; seed no rows.
2. Ship APIs; stop accepting `other_cost_percent` as costing input; update `calculate_package_totals` callers.
3. Remove or null-ignore `other_cost_percent` field (prefer drop after serializers/tests updated).
4. Existing draft plans: require operational month before summary/finalize.
5. Existing finalized plans: leave snapshots unchanged; reopen + re-finalize to adopt new other-cost basis.
6. Rollback: reverse migration only if no critical production dependence on new tables; code rollback restores percent formula (avoid if finalized snapshots mixed old/new semantics—prefer forward-fix).

## Open Questions

- Should per-meal operational cost quantize to `0.01` or keep 6 decimal places until package rollup? **Default in implementation: `0.01` for admin display and allocation.**
- Exact preview semantics for “selected ingredients cost” on a schedule slot (sum of flat+kg unit costs only vs share of package product cost)—specs will define one-meal unit cost sum; refine if product wants package-average instead.
- Whether to soft-delete cost items vs hard delete—default hard delete for draft month editing; no soft-delete unless audit requires it later.
