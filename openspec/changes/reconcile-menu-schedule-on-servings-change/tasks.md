## 1. Backend — reconcile service

- [x] 1.1 Add `reconcile_draft_schedule_after_plan_line_change(plan)` in `meals/services/menu_schedule.py`
- [x] 1.2 Implement deterministic trim: date DESC, dinner before lunch; delete empty slots
- [x] 1.3 Handle ingredients removed from plan (treat as quota 0, remove all items)
- [x] 1.4 Hook from `replace_plan_lines()` in `cycle_calculations.py` (capture old quotas before line delete, same transaction)

## 2. Backend — tests

- [x] 2.1 Test: 5→4 servings removes exactly 1 slot item, schedule preserved
- [x] 2.2 Test: servings to 0 / ingredient removed removes all items (screenshot: dim bhaji case)
- [x] 2.3 Test: increase servings does not add slot items
- [x] 2.4 Test: assignment save succeeds after reconcile (no over-quota block)
- [x] 2.5 Test: sibling package schedule untouched
- [x] 2.6 Run: `python manage.py test meals.tests.test_monthly_menu_schedule meals.tests.test_meal_cycle_api --keepdb`

## 3. Backend — documentation

- [x] 3.1 Update `meals/docs/backend/monthly-meal-menu-schedule.md` — auto-reconcile on servings save
- [x] 3.2 Update `meals/docs/backend/meal-cycle-management.md` — plan line save side effect

## 4. Frontend

- [x] 4.1 Ensure servings matrix save invalidates schedule detail + quota queries (verify `useReplaceAdminCyclePlanLines`)
- [x] 4.2 Optional toast when reconciliation removed assignments (if backend exposes count in response or infer from refetch)
- [x] 4.3 Verify OVER QUOTA banner clears after matrix save without manual calendar edit

## 5. Verification

- [x] 5.1 Manual: assign dim bhaji → reopen → set servings 0 → save matrix → open schedule → no OVER QUOTA, item gone
- [x] 5.2 Manual: 5→4 decrease → exactly one assignment removed, rest intact
- [x] 5.3 Manual: increase servings → no auto-added slots, remaining quota available
