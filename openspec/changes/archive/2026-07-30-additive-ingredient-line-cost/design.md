## Context

Meal-cycle costing lives in `meals/services/cycle_calculations.py`. Today `resolve_cost_per_customer` prefers kg pricing (`price_per_kg / customers_per_kg`) and otherwise returns flat `cost_per_customer`. `build_line_detail` multiplies that single value by `servings_count`. Ingredient API `resolved_cost_per_customer` uses the same helper, so clients treat kg and flat as mutually exclusive.

Product ops need **both** costs when present: material (kg-derived) plus optional cooking/piece cost (`cost_per_customer`). Downstream rollups (`product_cost` sum → other/profit/total/per-meal → finalize snapshots) stay the same; only the per-line unit input changes.

## Goals / Non-Goals

**Goals:**

- Implement additive unit cost: `(resolved_cost_per_customer + cost_per_customer) × servings_count` → `line_product_cost`.
- Make `resolved_cost_per_customer` mean **kg-only** (null when no complete kg pair).
- Treat a missing side as `0` in the sum when the other side exists; still reject ingredients with **neither** source on plan attach / summary / finalize.
- Update tests and backend/frontend docs so admin UI can preview and display the formula correctly.
- Keep Decimal money math and package rollup structure unchanged.

**Non-Goals:**

- New DB columns or renaming `cost_per_customer`.
- Recalculating already-finalized plan snapshots automatically.
- Changing other_cost / profit percents, operational cost allocation, or main-role servings rules.
- Customer-facing public meal APIs (they already omit internal costing bands).

## Decisions

### 1. Split “kg resolved” from “flat” in the service layer

- Add (or reshape) helpers so kg resolution never falls back to flat:
  - `resolved_kg_cost_per_customer(ingredient) -> Decimal | None`
  - Flat contribution: `Decimal(ingredient.cost_per_customer)` or `Decimal('0')` when null
  - `combined_unit_cost = (kg or 0) + (flat or 0)`
  - `line_product_cost = combined_unit_cost × servings_count` (existing quantize rules)
- Keep `ingredient_has_resolvable_cost` as “kg pair **or** flat present” (unchanged gate).
- Deprecate / rewrite `resolve_cost_per_customer` so callers cannot accidentally use the old exclusive semantics (prefer explicit combined helper used by `build_line_detail`).

**Alternatives considered:** Keep exclusive resolve and add a separate “cooking surcharge” field — rejected; product already stores flat as `cost_per_customer` and wants additive use of that field.

### 2. API field semantics

| Field | New meaning |
| --- | --- |
| `resolved_cost_per_customer` (ingredient) | Kg-only unit cost, or `null` if no kg pair |
| `cost_per_customer` (ingredient) | Stored flat cooking/piece cost; may be null; may coexist with kg |
| Summary line `line_product_cost` | `(coalesce(resolved,0) + coalesce(flat,0)) × servings_count` |
| Summary line unit fields | Expose both components used in the sum (resolved kg unit + flat), not a single exclusive unit |

**Alternatives considered:** Invent `combined_cost_per_customer` as a new persisted field — rejected; derive at read/calc time only.

### 3. Null handling inside the sum

- If only kg: `(resolved + 0) × servings`
- If only flat: `(0 + flat) × servings`
- If both: `(resolved + flat) × servings`
- If neither: validation error (no fabricated zero `product_cost`)

### 4. Docs deliverables

- Backend: update money-formula section in `meal-cycle-management.md`.
- Frontend: dedicated `meals/docs/frontend/additive-ingredient-line-cost.md` plus touch points in `ingredient-per-serving-cost.md` / `FRONTEND_IMPLEMENTATION.md`.

## Risks / Trade-offs

- **[BREAKING semantics]** Clients that assumed “resolved ignores flat when kg exists” will under-display cost until they update UI copy/math. → Mitigation: frontend doc + changelog wording; show both unit chips and combined preview.
- **[Higher product_cost]** Plans with both pricing sources will jump on next summary/finalize after reopen. → Mitigation: document; finalized snapshots stay frozen until reopen.
- **[Double-count confusion]** If admins historically stored flat equal to kg-derived cost as a duplicate, additive math double-counts. → Mitigation: document that flat is **additive cooking cost**, not a second copy of kg material cost; optional admin cleanup note in frontend doc.
- **[Helper rename churn]** Tests import `resolve_cost_per_customer`. → Mitigation: update tests in the same change; keep a thin wrapper only if needed for transitional clarity.

## Migration Plan

1. Ship service + serializer + test updates.
2. Deploy; no data migration required.
3. Admins reopen non-finalized plans (or reopen finalized) to see new summary numbers.
4. Frontend ships against new `resolved_cost_per_customer` meaning and additive preview.
5. Rollback: revert service commit; snapshots written under new formula remain until reopen (acceptable; document).

## Open Questions

- None blocking implementation; treat missing flat/kg side as `0` in the sum as specified above.
