# Serving Matrix Evaluation (Backend)

OpenSpec: `openspec/changes/dynamic-serving-matrix/`.

Frontend workflow: [`../frontend/FRONTEND_IMPLEMENTATION.md`](../frontend/FRONTEND_IMPLEMENTATION.md).

## Rules

1. `ensure_serving_profile(meal)` creates profile + `main eq expected_servings` when missing.
2. Aggregator sums plan-line `servings_count` by `product_role` and by non-null `ingredient_type`.
3. Target resolution:
   - `expected_servings` → `plan_expected_servings(plan) + target_offset`
   - `absolute` → `absolute_value`
4. Operators: `eq` / `lte` / `gte`.
5. Finalize calls `validate_serving_matrix_for_finalize` (all rows must be satisfied).
6. Menu slot writes call `validate_slot_item_count` for non-empty slots using profile min/max.

## Module

`meals/services/serving_matrix.py` — aggregate, evaluate, validate finalize & slot bounds.
