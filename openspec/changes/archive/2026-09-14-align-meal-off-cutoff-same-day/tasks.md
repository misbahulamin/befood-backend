## 1. Deadline helper and model defaults

- [x] 1.1 Update `meal_off_deadline` in `orders/services/meal_off.py` so lunch uses `service_date` (same day), not `service_date - 1 day`
- [x] 1.2 Update `MealOffSettings` field defaults to lunch `00:00:00` and dinner `16:00:00`, and revise help text/docstring to say both times apply on the service date
- [x] 1.3 Add Django migration: alter field defaults/help text; data-migrate singleton `pk=1` from exact legacy `(23:59, 14:00)` to `(00:00, 16:00)` with reverse for `(00:00, 16:00)` only

## 2. API copy and admin surfaces

- [x] 2.1 Update OpenAPI / view descriptions that still say lunch previous-day `23:59` or dinner `14:00` (e.g. meal-off action docs in `orders/api/views.py`)
- [x] 2.2 Confirm `MealOffSettingsSerializer` / admin list still expose `timezone`, `lunch_off_time`, `dinner_off_time` without contract renames

## 3. Tests

- [x] 3.1 Rewrite `MealOffDeadlineHelperTests` for same-day lunch at `00:00` and dinner at `16:00` (boundary inclusive / just-after cases for Off and On)
- [x] 3.2 Update API / service tests in `orders/tests/test_customer_meal_off.py` that hard-code previous-day lunch or `14:00` dinner expectations
- [x] 3.3 Update meal-demand tests (`orders/tests/test_meal_demand.py`) that assert lunch confirmation after prior-day `23:59` or dinner `14:00` defaults
- [x] 3.4 Add/adjust a settings test covering admin PATCH of `lunch_off_time` / `dinner_off_time` applying on the service date

## 4. Documentation

- [x] 4.1 Update `orders/docs/backend/customer-meal-off.md` default table and settings example (`00:00` / `16:00`, same-day lunch)
- [x] 4.2 Update related frontend/backend docs that cite old cut-offs (`orders/docs/frontend/customer-meal-off.md`, meal-demand kitchen docs, `auto-meal-delivery.md` notes)

## 5. Verification

- [x] 5.1 Run `python manage.py test orders.tests.test_customer_meal_off orders.tests.test_meal_demand` (and any other failing deadline-related tests) and fix regressions
- [x] 5.2 Smoke-check: admin GET meal-off settings shows new defaults; lunch `D` blocked after `D 00:00`; dinner `D` blocked after configured dinner time; `meal_off_deadline_at` matches helper
