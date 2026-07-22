## Context

BeFood already sells meal packages (`MealCategory`) and has a WIP admin `Ingredient` + `MealRecipe` API. The real business process lives in `menu analaytic chart.xlsx`:

1. **Product list** — per-kg price, customers per kg → cost per customer (`price ÷ customers`), optional pieces; some rows are flat cost-only (Vegetables, Dhal, Moshla, Egg With Jhul).
2. **Meal Type matrix (A–F)** — for each package, admin enters how many times each product is served in the cycle.
3. **Meal Price List** — line cost = `cost_per_customer × servings`.
4. **Final Meal Price List** — product cost sum + other cost (30%) + profit (10% or 20%) → total → divide by total meals for per-meal rate.

Excel hardcodes `60` meals. Product already has `meals/services/pricing.py` using `calendar.monthrange` and **2 meals/day**, which matches the user’s rule (Jan 31 → 62, Apr 30 → 60).

Current `MealRecipe.quantity_in_cycle` (kg) does not match how admins think or how Excel calculates.

Stakeholders: verified admins (planning/costing), backend team, future admin frontend.

## Goals / Non-Goals

**Goals:**

- Model month-scoped cycles with `total_meals = days_in_month × 2`.
- Let admins assign **serve counts** per product per meal package within a cycle.
- Compute Excel-equivalent line costs, package totals, overhead, profit, and per-meal rate with `Decimal`.
- Support finalize → return clear meal details summary for one meal package in that month.
- Keep public customer meal APIs unchanged in this change.
- Ship beginner-friendly backend documentation after implementation.

**Non-Goals:**

- Day-by-day menu calendar (which exact day serves Beef).
- Inventory / purchase orders / kitchen stock.
- Automatically overwriting public `MealCategory.total_price` on finalize (optional later; can expose suggested rate only).
- Multi-branch / multi-company costing.
- Importing the Excel file as a first-class product feature (seed/migration helper OK).

## Decisions

### 1. Domain model: Cycle → Plan → Lines (not kg recipes)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ MealCycle   │────▶│ MealCyclePlan    │────▶│ MealCyclePlanLine   │
│ year+month  │ 1:N │ meal_category    │ 1:N │ ingredient          │
│ days, meals │     │ margins, status  │     │ servings_count      │
└─────────────┘     └──────────────────┘     └─────────────────────┘
        │                     │
        │                     ▼
        │              computed summary
        │              (on read / finalize)
        ▼
┌─────────────┐
│ Ingredient  │  (product catalog)
└─────────────┘
```

- **MealCycle**: unique `(year, month)`; `cycle_days` and `total_meals` derived (stored for snapshot stability).
- **MealCyclePlan**: one plan per `(cycle, meal_category)`; holds `other_cost_percent` (default 30), `profit_percent` (default 10 or 20 by package policy), `status` (`draft` | `finalized`).
- **MealCyclePlanLine**: `(plan, ingredient)` unique; primary input `servings_count` (≥ 0 integer).

**Why not extend MealRecipe?** Recipe-as-kg fights Excel math and month variability. A cycle-scoped plan matches the spreadsheet’s “one month sheet” mental model.

**Alternative considered:** Keep global recipes without months, only pass `?month=` for display. Rejected — January vs April change totals and validation; plans must be month-owned.

### 2. Cost-per-customer on Ingredient

- If `price_per_kg` and `customers_per_kg` are set → `cost_per_customer = price_per_kg / customers_per_kg`.
- Else allow explicit `cost_per_customer` (flat items).
- Validation: at least one complete pricing mode must be present; reject incomplete kg mode.
- Optional `product_role`: `main` | `side` | `staple` | `seasoning` | `other` to support Excel’s “Total meal” check (sum of **main** protein servings ≈ `total_meals`).

**Alternative:** Always require kg fields and fake kg for vegetables. Rejected — Excel explicitly uses flat costs.

### 3. Formulas (service layer, Decimal)

| Output | Formula |
| --- | --- |
| `cost_per_customer` | `price_per_kg / customers_per_kg` or stored flat |
| `line_product_cost` | `cost_per_customer × servings_count` |
| `product_cost` | sum of line costs |
| `other_cost` | `product_cost × other_cost_percent / 100` |
| `profit` | `product_cost × profit_percent / 100` |
| `total_cost` | `product_cost + other_cost + profit` |
| `per_meal_rate` | `total_cost / cycle.total_meals` |

Reuse patterns from `pricing.get_present_month_days`; add `get_month_days(year, month)` and `total_meals_for_month`.

Optional derived: `estimated_kg = servings_count / customers_per_kg` when kg mode exists (helpful detail, not primary input).

### 4. Finalize semantics

- `POST .../finalize` on a plan: validates rules, sets `status=finalized`, snapshots key totals on the plan row (immutable display even if ingredient prices later change—unless `reopen`/`recalculate` is added later).
- Draft plans recalculate live from current ingredient prices.
- Finalized plans reject line edits until `POST .../reopen` (admin-only), which returns to draft.

**Validation on finalize (configurable but default on):**

- Sum of `servings_count` for `product_role=main` MUST equal `cycle.total_meals` (Excel protein fill rule).
- Optional soft warning (not hard fail) if staples ≠ `total_meals`.

### 5. API shape (admin-only, `IsVerifiedAdmin`)

Prefer resource nouns under `/meals/`:

| Resource | Endpoints |
| --- | --- |
| Ingredients | existing CRUD, extended fields |
| Cycles | `GET/POST /meals/cycles/`, `GET/PATCH /meals/cycles/{id}/` |
| Plans | `GET/POST /meals/cycle-plans/`, detail + patch margins |
| Lines | nested or filtered `GET/POST/PATCH/DELETE` under plan / `cycle-plan-lines/` |
| Actions | `POST /meals/cycle-plans/{id}/finalize`, `POST .../reopen`, `GET .../summary` |

**BREAKING:** Deprecate `/meals/recipes/` (or make it read-only shim). Prefer remove after migration of WIP data.

Bulk upsert for lines (matrix save) is allowed as `PUT /meals/cycle-plans/{id}/lines` replacing the matrix in one transaction—mirrors Excel edit UX.

### 6. Documentation deliverable

After APIs work, write `meals/docs/backend/meal-cycle-management.md` following project backend-doc outline: mental model, formulas with numeric example (Apr 30 → 60 meals), permission matrix, every endpoint with request/response, workflow order (login → ingredients → create cycle → create plan → set servings → summary → finalize), errors, verification checklist. Supersede root `docs/meal-ingredients-recipes-api.md` with a pointer.

## Risks / Trade-offs

- **[Risk] Breaking WIP recipe API** → Mitigation: admin-only, document migration; drop or migrate `MealRecipe` rows in same change.
- **[Risk] Excel “Total meal” formula range is inconsistent across columns** → Mitigation: encode explicit `product_role=main` instead of row-number heuristics.
- **[Risk] Price changes after finalize confuse finance** → Mitigation: snapshot totals on finalize; document that draft is live.
- **[Risk] Profit % differs by package (A–C 20%, D–F 10% in sample)** → Mitigation: store `profit_percent` per plan with sensible defaults; admin can override.
- **[Trade-off] No daily menu calendar** → Admins get costing/serve counts only; day assignment is a future capability.

## Migration Plan

1. Expand `Ingredient` fields (`cost_per_customer` nullable, `product_role`, relax required kg fields with constraints).
2. Add `MealCycle`, `MealCyclePlan`, `MealCyclePlanLine` + migrations.
3. Data: keep existing ingredients; do not auto-convert kg recipes (WIP). Delete or ignore `MealRecipe` after admin confirmation.
4. Ship new endpoints; remove/deprecate recipe routes in same PR if unused in production.
5. Docs + tests green before merge.
6. Rollback: reverse migration; recipe code only restorable from git if still needed.

## Open Questions

- Should finalize optionally write suggested `per_meal_rate × total_meals` into `MealCategory.total_price`? **Default: no** (suggestion only in summary).
- Exact default `profit_percent` per existing seeded packages — map from Excel A–F labels to real `MealCategory` names during seed/docs.
- Is `reopen` required in v1, or is “delete plan and recreate” enough? **Prefer reopen** for admin UX.
- Should `Cooking Cost` / `Kitchen Cost` blank rows in Excel become first-class line items or stay inside the 30% other-cost bucket? **Default: stay in other-cost %** unless admin needs explicit lines later.
