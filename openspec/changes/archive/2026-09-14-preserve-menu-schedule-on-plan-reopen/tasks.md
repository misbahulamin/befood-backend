## 1. Backend — reopen preserves schedule

- [x] 1.1 Remove draft `MonthlyMenuSchedule` deletion from `reopen_plan()` in `meals/services/cycle_calculations.py` (keep published-schedule rejection guard)
- [x] 1.2 Confirm `replace_plan_lines()` and `finalize_plan()` do not touch schedule rows (no extra change expected; note in PR if verified only)

## 2. Backend — tests

- [x] 2.1 Replace `test_reopen_deletes_draft_schedule` with `test_reopen_preserves_draft_schedule` — assert schedule + assignments survive reopen
- [x] 2.2 Add test: reopen → `PUT .../lines` (servings change) → schedule assignments unchanged
- [x] 2.3 Add test: reopen → finalize again → exactly one schedule, assignments intact
- [x] 2.4 Verify existing `test_reopen_blocked_when_schedule_published` still passes unchanged
- [x] 2.5 Run targeted suite: `python manage.py test meals.tests.test_monthly_menu_schedule meals.tests.test_meal_cycle_api meals.tests.test_cycle_calculations`

## 3. Backend — documentation

- [x] 3.1 Update reopen section in `meals/docs/backend/meal-cycle-management.md` — draft schedule preserved
- [x] 3.2 Update reopen note in `meals/docs/backend/monthly-meal-menu-schedule.md`

## 4. Frontend — copy and UX

- [x] 4.1 Update reopen confirm dialog in `AdminCyclePlanEditorPage.tsx` — remove destructive schedule-delete warning
- [x] 4.2 Update inline schedule hint text on plan editor (line ~360) — schedule preserved on reopen
- [x] 4.3 Smoke-check plan editor: reopen with draft schedule → navigate to menu schedule → assignments visible

## 5. Verification

- [x] 5.1 Manual regression: finalize → create schedule → assign days → reopen → verify calendar intact
- [x] 5.2 Manual regression: reopen → change servings → verify calendar intact and summary recalculates
- [x] 5.3 Manual regression: reopen → finalize → single schedule, no duplicate create error
- [x] 5.4 Confirm sibling package schedules unaffected (existing isolation tests green)

## 6. Frontend follow-up — schedule visibility after reopen (screenshot regression)

- [x] 6.1 Show **Open menu schedule** when `linkedSchedule` exists even while plan is `draft` (not only when finalized)
- [x] 6.2 Invalidate `adminMenuSchedulesQueryKeys` on **finalize** and **replace lines** (stale cache showed "Create menu schedule")
- [x] 6.3 `AdminMenuSchedulePage`: allow viewing/editing existing draft schedule when plan is draft after reopen
- [x] 6.4 Draft banner: show preserved-schedule message instead of "available after finalize" when schedule exists
