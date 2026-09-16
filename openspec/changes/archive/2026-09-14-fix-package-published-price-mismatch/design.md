## Context

### Investigation summary (root cause)

Package summary fields are computed in `meals/services/cycle_calculations.py`:

| Field | Source | Formula |
| --- | --- | --- |
| Product Cost | Live or snapshot | Σ `line_product_cost` per plan line |
| Other Cost | Live or snapshot | `expected_servings × per_meal_operational_cost` |
| Profit | Live or snapshot | `product_cost × profit_percent / 100` |
| Total Cost | Live or snapshot | `product_cost + other_cost + profit` |
| Per Meal Rate | Live or snapshot | `total_cost / expected_servings` (quantized) |
| Published Meal Price | **Always** `MealCategory.total_price` | Updated **only** on `finalize_plan` → `publish_meal_price_from_plan` |

**Key code paths:**

```python
# calculate_package_totals (cycle_calculations.py)
profit = product_cost × profit_percent / 100   # product cost only — intentional per spec
total_cost = product_cost + other_cost + profit
per_meal_rate = total_cost / expected_servings

# build_plan_summary
suggested_package_price = round(per_meal_rate) × servings   # secondary rounding drift
published_meal_total_price = meal_category.total_price      # stale until re-finalize
```

### Reproducing the reported numbers

| Component | Old (published) | Current (live) |
| --- | --- | --- |
| Product Cost | 2533.29 | 2533.29 |
| Other Cost | **200.38** | **247.80** |
| Per-Meal Op Cost | **~3.34** | **4.13** |
| Profit (15%) | 379.99 | 379.99 |
| **Total / Published** | **3113.66** | **3161.08** |

Gap: **247.80 − 200.38 = 47.42 = 3161.08 − 3113.66**

The mismatch is **exactly** the operational-cost increase since the last finalize. The summary recalculates live totals (draft plan, or post-reopen draft) using the current month's `per_meal_operational_cost`, but `published_meal_total_price` still reflects the last finalized `snapshot_total_cost` written to `MealCategory.total_price`.

On a **finalized** plan, snapshot and published price are consistent (tests confirm `meal.total_price == snapshot_total_cost` after finalize). The bug manifests when admins compare live draft totals against a stale published price without re-finalizing.

### Profit on product cost only

This is **intentional**, not a bug. `openspec/specs/meal-cycle-costing/spec.md` and `calculate_package_totals` docstring both define:

```text
profit = product_cost × profit_percent / 100
```

Margin on full package cost (including op allocation) would be lower than `profit_percent`; the UI label "Target profit margin 15%" refers to markup on product/ingredient cost.

### Secondary issue: `suggested_package_price` rounding

`round(per_meal_rate) × servings` can differ from `total_cost` by up to ~(servings × 0.005) taka. For the example: 52.68 × 60 = 3160.80 vs total 3161.08 (৳0.28 drift). Not the user's ৳47.42 gap, but should be fixed for consistency.

## Goals / Non-Goals

**Goals:**

- Make published vs total cost relationship explicit in the summary API.
- Prevent admins from misreading draft live totals as the current selling price.
- Fix `suggested_package_price` to equal `total_cost`.
- Add regression tests for op-cost-change → stale published price scenario.
- Correct outdated backend documentation.

**Non-Goals:**

- Changing profit formula (product-cost-only base stays).
- Auto-re-finalizing or auto-publishing when operational cost ledger changes.
- Frontend implementation (document contract; frontend team applies labels/warnings).
- Migrating historical `MealCategory.total_price` values in production (ops re-finalize as needed).

## Decisions

### 1. Add sync metadata to summary (not silent auto-fix)

**Choice:** Add `published_price_status` (`in_sync` | `stale`) and `published_price_delta` (decimal string, nullable) to `build_plan_summary` response.

- `in_sync`: `published_meal_total_price == total_cost` (or both null)
- `stale`: draft live `total_cost` differs from `meal_category.total_price`
- `delta` = `total_cost − published_meal_total_price` when stale

**Alternatives considered:**

- Auto-update `meal.total_price` on every summary read → rejected (side effects on GET, breaks reopen semantics).
- Hide published price on draft plans → rejected (admins need to see what customers currently pay).

### 2. Fix `suggested_package_price` = `total_cost`

**Choice:** Replace `round(per_meal_rate) × servings` with `total_cost` directly.

**Rationale:** Package price is authoritative at total level; per-meal rate is derived.

### 3. Optional: `realized_profit_margin_percent` on summary

**Choice:** Add computed field when published price is stale:

```text
realized_profit = published_meal_total_price − product_cost − other_cost
realized_margin = realized_profit / product_cost × 100
```

Helps admins see the 11.96% vs 15% gap without manual calculation. Informational only.

### 4. Validation on finalize (assert invariant)

**Choice:** After `publish_meal_price_from_plan`, assert `meal.total_price == plan.snapshot_total_cost`. Already implicit; add explicit test.

### 5. Tests

| Test | Asserts |
| --- | --- |
| `test_finalize_published_equals_total_cost` | Existing; keep |
| `test_draft_summary_stale_published_after_op_cost_change` | Finalize at op 3.34 → change ledger to 4.13 → draft summary: `published_price_status=stale`, delta matches |
| `test_suggested_package_price_equals_total_cost` | No rounding drift |
| `test_profit_base_is_product_cost_only` | Document intentional behavior |

## Risks / Trade-offs

- **[Risk] Admins may have been selling at stale prices** → Mitigation: `published_price_status` surfaces the gap; ops should re-finalize affected plans after op-cost updates.
- **[Risk] Frontend must adopt new fields** → Mitigation: additive API; old clients unaffected but should update labels.
- **[Risk] Re-finalize required after op-cost change** → By design (snapshot model); document in admin workflow.

## Migration Plan

1. Deploy backend with new summary fields (backward compatible).
2. Update frontend to show warning badge when `published_price_status=stale`.
3. Ops: identify packages where stale; reopen + finalize to publish new price.
4. No DB migration required.

## Open Questions

1. Should profit margin UI say "15% on product cost" instead of generic "target margin"? (Product/UX decision.)
2. Should operational-cost month edits trigger a notification to re-finalize affected draft/finalized plans? (Out of scope for this fix.)
