## Context

The ingredient catalog already stores per-serving money as `cost_per_customer`, plus optional kg inputs (`price_per_kg`, `customers_per_kg`) that resolve to the same figure. Model and serializer validation currently **require** either a complete kg pair or a flat `cost_per_customer`, so admins cannot save a catalog row until pricing is known.

Product ask: when creating an ingredient, expose an optional input for “how much this ingredient costs to cook for one customer or one piece,” and allow leaving it empty. Meal-cycle math still depends on a resolvable cost when the ingredient is used on a plan.

Stakeholders: verified admins (catalog + cycle planning), admin web form, costing services.

## Goals / Non-Goals

**Goals:**

- Make catalog pricing optional: create/update with name (and other non-price fields) only.
- Keep `cost_per_customer` as the single optional flat per-serving cost field (one customer or one piece).
- Preserve kg-pair completeness and “kg wins over stored flat when resolving.”
- Fail loudly at plan-line write and summary/finalize when cost cannot be resolved.
- Document field meaning for API and admin UI.

**Non-Goals:**

- New parallel column (e.g. `cooking_cost`) or currency multi-support.
- Automatic derivation of piece cost from `pieces_per_kg` (no new formula in this change).
- Changing customer/public menu payloads to expose ingredient costs.
- Recalculating historical finalized snapshots when catalog cost is later filled in (existing finalize/reopen rules stay).

## Decisions

### 1. Reuse `cost_per_customer` instead of adding a new field

- **Choice:** Optional flat cost continues to live on `Ingredient.cost_per_customer`.
- **Why:** Semantics already match “cost per customer serving”; piece-based products use the same per-unit cost when each line serving is one piece. A second money field would duplicate storage and confuse APIs.
- **Alternatives considered:** New `cooking_cost_per_unit` — rejected as redundant; rename field — rejected as unnecessary **BREAKING** churn for the same meaning.

### 2. Catalog vs costing validation split

- **Choice:** Catalog create/update allows all pricing fields null/omitted. Costing paths (`resolve_cost_per_customer`, plan line validate, summary/finalize) still require a resolvable cost.
- **Why:** Matches “optional when cataloging, required when costing.” Avoids silently treating missing cost as `0`, which would understate package price.
- **Alternatives considered:** Allow plan lines with zero cost — rejected (hides data gaps); require cost only on finalize — weaker (draft summaries would also break or lie).

### 3. Where to reject missing cost

- **Choice:** Validate on plan-line create/replace **and** keep `resolve_cost_per_customer` raising if somehow invoked without cost (defense in depth for summary/finalize).
- **Why:** Admin gets immediate feedback when attaching an unpriced ingredient; summary remains safe if data drifts.

### 4. `resolved_cost_per_customer` when catalog has no pricing

- **Choice:** Serializer method field returns `null` when cost cannot be resolved (already catches exceptions loosely); do not invent `0`.
- **Why:** List/detail can show “cost unknown” without failing the whole catalog list.

### 5. Money rules unchanged when value is present

- Flat `cost_per_customer` when provided: `> 0`, decimal money rules as today.
- Kg pair: both or neither; resolved cost = `price_per_kg / customers_per_kg`.
- No migration of existing rows required (all current rows already satisfy old stricter rule).

## Risks / Trade-offs

- **[Risk]** Admins build a full servings matrix then discover missing costs late → **Mitigation:** reject at line write with ingredient name in the error; docs call out “fill cost before attaching to a plan.”
- **[Risk]** Frontend still treats pricing as required → **Mitigation:** frontend doc states field is optional; OpenAPI marks nullable/not required.
- **[Risk]** Confusion between stored flat cost and kg-derived cost → **Mitigation:** keep `resolved_cost_per_customer` as the display/costing source of truth; help text clarifies kg overrides flat when kg pair is complete.

## Migration Plan

1. Relax `Ingredient.clean` and `IngredientSerializer.validate` (no DB schema change required; field already `null=True, blank=True`).
2. Add plan-line validation for resolvable cost.
3. Update tests and docs.
4. Deploy: backward compatible for existing clients that always send pricing; clients that omit pricing start working.
5. Rollback: re-enable “must have kg or flat” validation only (no data loss).

## Open Questions

- None blocking implementation. If product later wants piece cost derived from `price_per_kg / pieces_per_kg`, that is a separate change.
