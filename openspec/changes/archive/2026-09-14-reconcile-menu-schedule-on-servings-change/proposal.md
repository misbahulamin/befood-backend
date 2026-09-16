## Why

After `preserve-menu-schedule-on-plan-reopen`, draft menu schedules survive plan reopen and servings edits — but assignments are **not reconciled** when plan-line `servings_count` decreases or an ingredient is removed. The schedule still references the old usage count, causing **OVER QUOTA** errors (e.g. "রেগুলার ডিম ভাজি used 1 times but plan allows 0") and blocking save/publish. Admins expect incremental adjustment: reduce egg curry 5→4 → remove one slot assignment; reduce to 0 or remove ingredient → strip all its assignments — without deleting the whole schedule or rebuilding the calendar.

## What Changes

- **Backend service:** Add `reconcile_draft_schedule_after_plan_line_change()` in `meals/services/menu_schedule.py`. When `replace_plan_lines()` saves a new servings matrix, automatically trim excess `MonthlyMenuSlotItem` rows for ingredients whose new quota is lower than current schedule usage. Remove all assignments for ingredients no longer on the plan or with `servings_count = 0`.
- **Trim order (deterministic):** Remove excess assignments from **latest calendar slots first** (`service_date` descending, then `dinner` before `lunch`). Delete empty slot rows after item removal.
- **No auto-add on increase:** When servings increase or a new ingredient is added to the plan, the schedule is unchanged — admin assigns new slots manually (quota headroom only).
- **Guards:** Only reconcile **draft** schedules linked to the plan; skip published schedules (plan must be draft to edit lines anyway). Run inside the same transaction as `replace_plan_lines()`.
- **Tests:** Cover decrease-by-one, decrease-to-zero, ingredient removed from plan, no-op when usage already within quota, sibling schedule isolation.
- **Frontend:** Invalidate schedule detail/quota queries after servings matrix save; optional toast when reconciliation removed assignments (if API exposes count). OVER QUOTA banner should clear after save without manual slot editing.
- **Docs:** Update meal-cycle and menu-schedule backend docs; note reconciliation runs on servings save, not on schedule delete.

No database migration. No API contract break (same endpoints; `PUT .../lines` gains non-destructive side effect on linked draft schedule).

Depends on: `preserve-menu-schedule-on-plan-reopen` (schedule must exist to reconcile).

## Capabilities

### New Capabilities

_(none — behavior extends existing menu-schedule + plan-line workflows)_

### Modified Capabilities

- `monthly-menu-schedule`: Draft schedule assignments MUST auto-reconcile when linked plan lines change and usage exceeds new quotas.
- `meal-cycle-planning`: Servings matrix save (`replace_plan_lines`) MUST trigger draft schedule reconciliation without deleting the schedule.

## Impact

| Area | Change |
| --- | --- |
| `meals/services/menu_schedule.py` | New reconcile function |
| `meals/services/cycle_calculations.py` | Hook reconcile after `replace_plan_lines()` |
| `meals/tests/test_monthly_menu_schedule.py` | Reconciliation regression tests |
| `meals/docs/backend/` | Document auto-trim behavior |
| `befood-frontend` | Cache invalidation + optional reconciliation feedback after matrix save |

**Screenshot symptom:** Ingredient at `planned=0, used=1` with OVER QUOTA → caused by missing reconciliation after plan line reduced to 0.
