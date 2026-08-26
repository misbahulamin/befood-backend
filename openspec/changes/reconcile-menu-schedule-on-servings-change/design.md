## Context

Production flow after `preserve-menu-schedule-on-plan-reopen`:

1. Finalize plan → create draft `MonthlyMenuSchedule` → assign day-wise ingredients
2. Reopen plan → edit servings matrix → `replace_plan_lines()` replaces `MealCyclePlanLine` rows
3. Schedule slot items (`MonthlyMenuSlotItem`) still reflect **old** usage counts
4. Admin opens menu schedule → quota summary shows `over_quota: true` → save blocked

Current validation in `_validate_assignment_matrix()` rejects `used > planned` on explicit assignment PUT, but nothing trims existing DB rows when plan quotas shrink.

Data model:

- `MonthlyMenuSchedule` 1:1 `MealCyclePlan`
- `MonthlyMenuSlot` per `(service_date, meal_period)`
- `MonthlyMenuSlotItem` per `(slot, ingredient)` — one row = one slot usage of that ingredient

## Goals / Non-Goals

**Goals:**

- On servings matrix save, auto-trim draft schedule so `used ≤ planned` for every ingredient on the plan
- Ingredient removed from plan or `servings_count = 0` → remove **all** its slot items
- Ingredient decreased (e.g. 5→4) → remove exactly `(old_usage - new_planned)` slot items, deterministic order
- Preserve all other assignments unchanged
- Empty slots (no items left) deleted
- Idempotent: saving same matrix twice does not over-trim

**Non-Goals:**

- Auto-placing new ingredients when servings increase (admin assigns manually)
- Reconciling published schedules (blocked by plan edit guard)
- Changing quota validation rules on manual assignment PUT
- Cross-package schedule changes (`monthly-menu-package-isolation` unchanged)

## Decisions

### 1. Reconcile on `replace_plan_lines()`, not on schedule GET

**Choice:** Hook immediately after plan lines are recreated in `replace_plan_lines()`.

**Why:** Admin saves matrix → schedule is already consistent before opening menu schedule page. Avoids lazy surprises and matches user expectation ("komiye dibe" happens when they save plan, not when they open calendar).

**Alternative rejected:** Reconcile on schedule retrieve — would leave OVER QUOTA visible until page load; harder to test; two code paths.

### 2. Trim algorithm

```text
For each ingredient_id with current_usage > new_planned:
  excess = current_usage - new_planned
  List slot-items for that ingredient ordered by:
    service_date DESC, dinner before lunch (meal_period DESC)
  Delete first `excess` MonthlyMenuSlotItem rows
After all trims:
  Delete MonthlyMenuSlot rows with zero items
```

**Removal order rationale:** Latest month-end / dinner-first matches "peel from the end of the calendar" — predictable for admins and tests.

**Ingredient off plan:** `new_planned = 0` → remove all items for that ingredient (same loop with `excess = current_usage`).

### 3. Capture old quotas before line delete

In `replace_plan_lines()`:

```python
old_quotas = {line.ingredient_id: line.servings_count for line in plan.lines.all()}
# delete + recreate lines
reconcile_draft_schedule_after_plan_line_change(plan, old_quotas=old_quotas)
```

New quotas read from fresh plan lines inside reconcile function.

### 4. Response metadata (optional, additive)

Return reconciliation summary from service for logging/tests. Optionally extend `PUT .../lines` response with:

```json
"schedule_reconciliation": {
  "schedule_public_id": "...",
  "items_removed": 3,
  "ingredients_trimmed": [{"ingredient_id": 12, "removed": 1}]
}
```

**Non-breaking** additive field on plan lines response or separate internal only for v1 — design prefers **internal return + tests** first; frontend toast can use invalidation + refetch without new field.

### 5. Frontend

- `useReplaceAdminCyclePlanLines` already invalidates menu schedule queries (from prior change)
- After matrix save, refetch schedule detail — OVER QUOTA should be gone
- Optional toast: "Menu schedule updated: N assignments removed to match new servings"

## Risks / Trade-offs

- **[Risk] Removing a main leaves slot without main** → Mitigation: draft allows incomplete slots; publish still validates; admin fills gaps
- **[Risk] Admin prefers specific slot removed, not latest** → Mitigation: document deterministic order; admin can reassign after trim
- **[Risk] Trim during concurrent schedule edit** → Mitigation: `select_for_update` on schedule in same transaction as line replace
- **[Risk] Orphan ingredient in schedule not on plan** → Mitigation: treat as `new_planned = 0`, remove all

## Migration Plan

1. Deploy backend reconcile hook — no migration
2. Deploy frontend cache invalidation (if not already)
3. Existing over-quota drafts self-heal on next servings matrix save

## Open Questions

- _(none blocking)_ — Product confirmed incremental trim, not full schedule reset.
