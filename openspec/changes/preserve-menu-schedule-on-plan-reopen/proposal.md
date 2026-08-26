## Why

Admins finalize a cycle plan, build a monthly menu schedule (day-wise lunch/dinner assignments), then sometimes need to reopen the plan to adjust servings or margins. Today, reopening **deletes** the draft `MonthlyMenuSchedule` and all slot assignments — forcing admins to rebuild the calendar from scratch. This is destructive, contradicts production workflow expectations, and the frontend warning (`Reopening will delete the draft menu schedule…`) encodes that lossy behavior. Servings edits appear to wipe schedule data because reopen is required first and reopen is what deletes the schedule; `replace_plan_lines` does not touch schedule rows.

## What Changes

- **Backend:** Remove intentional draft schedule deletion from `reopen_plan()` in `meals/services/cycle_calculations.py`. Reopen continues to clear plan cost snapshots and return the plan to `draft`; published meal price remains until the next finalize. Block reopen only when the linked schedule is **published** (unchanged guard).
- **Backend:** Confirm `replace_plan_lines()` and finalize/reopen cycles do not cascade-delete or reset `MonthlyMenuSchedule` / slot assignments. Quota validation on assignment save and publish remains the safety net when servings shrink.
- **Backend:** Update `test_reopen_deletes_draft_schedule` → assert schedule **preserved** with assignments intact. Add regression tests for servings change + re-finalize preserving schedule.
- **Frontend (`befood-frontend`):** Update reopen confirmation copy and inline hints in `AdminCyclePlanEditorPage.tsx` — no longer warn about schedule deletion. Keep published-schedule unpublish guard.
- **Docs:** Update `meals/docs/backend/meal-cycle-management.md` and `monthly-meal-menu-schedule.md` reopen section to describe preserved schedule behavior.
- **Specs:** Change `meal-cycle-planning` reopen requirement from "delete/clear draft schedule" to "preserve draft schedule and assignments."

No database migration. No API contract break (same endpoints; behavior becomes non-destructive). **BREAKING (behavioral, admin-only):** Reopen no longer deletes draft menu schedules — clients that relied on implicit cleanup must delete schedules explicitly if desired.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `meal-cycle-planning`: Reopen with draft schedule MUST preserve schedule and assignments instead of deleting/clearing them.
- `monthly-menu-schedule`: Clarify that draft schedules survive plan reopen and servings edits; quota/publish guards enforce consistency after edits.

## Impact

| Area | Files / systems |
| --- | --- |
| Backend service | `meals/services/cycle_calculations.py` — `reopen_plan()` |
| Backend tests | `meals/tests/test_monthly_menu_schedule.py`, `meals/tests/test_meal_cycle_api.py` |
| Backend docs | `meals/docs/backend/meal-cycle-management.md`, `monthly-meal-menu-schedule.md` |
| Frontend | `befood-frontend/src/features/admin/pages/AdminCyclePlanEditorPage.tsx` |
| OpenSpec | Delta specs under this change; sync to `openspec/specs/` on archive |
| Production data | No migration; existing schedules unaffected; future reopens stop deleting data |

**Root cause (identified):** `reopen_plan()` lines 408–420 explicitly call `schedule.delete()` for draft schedules with comment "Draft schedule would become quota-orphan after line edits — delete it." Frontend mirrors this with destructive confirm dialog. Servings matrix save (`replace_plan_lines`) only replaces `MealCyclePlanLine` rows and does not delete schedules — the perceived servings→schedule reset is a reopen side effect.
