## 1. Models and migration

- [x] 1.1 Add `MonthlyMenuSchedule`, `MonthlyMenuSlot`, `MonthlyMenuSlotItem`, and `MenuRevealSettings` models in `meals/models.py` with unique constraints and statuses from design
- [x] 1.2 Generate and apply migration; register models in admin if the project registers peer meal models
- [x] 1.3 Wire reopen guard on `MealCyclePlan`: block reopen when linked schedule is published; delete draft schedule (or clear+delete) when reopening

## 2. Schedule quota and lifecycle services

- [x] 2.1 Implement `meals/services/menu_schedule.py`: quota usage, one-main-per-slot, ingredient-must-be-on-plan, bulk replace assignments
- [x] 2.2 Implement publish / unpublish validation (every date×period has exactly one main; return incomplete slot list on failure)
- [x] 2.3 Implement quota-summary helper (`planned`, `used`, `remaining`, `lunch_count`, `dinner_count` per ingredient)

## 3. Admin schedule APIs

- [x] 3.1 Add serializers and `IsVerifiedAdmin` viewsets for menu schedules (CRUD create requires finalized plan; one schedule per plan)
- [x] 3.2 Add `PUT .../assignments/`, `GET .../quota-summary/`, `POST .../publish/`, `POST .../unpublish/` actions
- [x] 3.3 Register routes under `/meals/` and Swagger tag **Admin Meal Menu Schedule**

## 4. Cross-package sync

- [x] 4.1 Implement `meals/services/menu_sync.py`: mirror mains/sides within target quotas, balance heuristic, divergence warnings
- [x] 4.2 Add `POST .../sync-suggestions/` and `POST .../apply-sync/` on schedule; apply transactional with same validation as bulk assign
- [x] 4.3 Cover unequal-quota case (e.g. chicken 12 vs 10) in service tests

## 5. Reveal settings and customer today menu

- [x] 5.1 Implement reveal settings singleton service + admin `GET/PATCH /meals/menu-reveal-settings/` with defaults 08:00 / 16:00 and business timezone
- [x] 5.2 Implement today-menu eligibility using active non-cancelled orders covering business-local today
- [x] 5.3 Add `GET /meals/today-menu/` for verified customers; lean payload; respect published schedule + reveal windows
- [x] 5.4 Ensure full-month schedule endpoints reject customers and anonymous users

## 6. Tests

- [x] 6.1 API tests: create schedule only from finalized plan; quota overflow; duplicate main; publish gates
- [x] 6.2 API tests: reopen blocked when schedule published; reopen deletes/clears draft schedule
- [x] 6.3 API tests: sync suggestion + apply; divergence warning
- [x] 6.4 API tests: reveal boundaries (before lunch, lunch-only, after dinner); today-menu auth and order scope

## 7. Documentation

- [x] 7.1 Write `meals/docs/backend/monthly-meal-menu-schedule.md` (mental model, permissions, workflows, examples, errors, verification)
- [x] 7.2 Cross-link from `meals/docs/backend/meal-cycle-management.md` to the new monthly schedule doc
