## Why

Admins often need to catalog ingredients before they know (or care about) cooking cost for one customer / one piece. Today the ingredient catalog **requires** either a kg pricing pair or a flat `cost_per_customer`, which blocks creating incomplete catalog entries and makes the per-serving cost feel mandatory instead of optional.

## What Changes

- Treat **per-serving cooking cost** (`cost_per_customer`) as an **optional** ingredient field: admins may set it when known, or leave it empty when not needed.
- Allow creating/updating an ingredient with **no pricing at all** (neither kg pair nor flat `cost_per_customer`).
- Keep existing kg pricing rules: if either `price_per_kg` or `customers_per_kg` is sent, both must be present; when the kg pair is complete, resolved cost continues to come from `price_per_kg / customers_per_kg`.
- When a flat `cost_per_customer` is provided, it MUST be greater than zero (same as today).
- Meal-cycle plan lines / costing MUST still require a **resolvable** per-serving cost when an ingredient is used on a plan — empty catalog cost remains catalog-only until pricing is filled in.
- Clarify API/docs/admin copy that `cost_per_customer` means total cooking cost for **one customer serving or one piece**, depending on how the product is used.
- Update backend + frontend docs and tests for optional pricing and plan-line rejection when cost is missing.
- No new duplicate money field; reuse existing `cost_per_customer` (not a second parallel cost column).

## Capabilities

### New Capabilities

<!-- None — this extends the existing ingredient catalog contract. -->

### Modified Capabilities

- `ingredient-catalog`: Make flat per-serving cooking cost optional; allow ingredients with no pricing; keep kg-pair completeness rule; document semantic as cost for one customer or one piece.
- `meal-cycle-planning`: When attaching a plan line whose ingredient has no resolvable cost, reject with a clear validation error instead of assuming zero.
- `meal-cycle-costing`: Summary/finalize MUST fail clearly when any line ingredient has no resolvable per-serving cost (do not treat missing cost as zero).

## Impact

- **Models / validation:** `Ingredient.clean` and `IngredientSerializer.validate` — drop “must have kg pair or flat cost” on create/update.
- **Services:** `resolve_cost_per_customer` / plan line build & finalize paths — fail clearly when cost is missing at costing time.
- **API:** `IngredientSerializer` request/response already exposes `cost_per_customer`; behavior becomes optional; OpenAPI examples/docs update.
- **Admin:** Django admin form help text / optional display for `cost_per_customer`.
- **Tests:** Catalog create without pricing; create with optional flat cost; plan-line/costing rejection when unresolved.
- **Docs:** `meals/docs/backend/meal-cycle-management.md`, frontend ingredient/cycle docs.
- **Clients:** Admin web ingredient form can show optional “cost per customer / piece” input; meal-cycle UI must handle missing-cost validation when adding lines.
