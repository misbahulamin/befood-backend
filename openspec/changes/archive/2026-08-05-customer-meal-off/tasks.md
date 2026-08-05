## 1. Models and migrations

- [x] 1.1 Add `MealOffSettings` singleton (`timezone`, `lunch_off_time` default 23:59, `dinner_off_time` default 14:00) with load/get_or_create pattern
- [x] 1.2 Add `OrderDelivery.skip_source` (`customer` | `admin`, nullable) and register in admin
- [x] 1.3 Create and apply migrations

## 2. Deadline helpers

- [x] 2.1 Implement `get_meal_off_settings`, `meal_off_deadline(service_date, meal_period)`, and `can_meal_off(delivery, now=...)` using settings timezone
- [x] 2.2 Unit-test lunch previous-day 23:59 and dinner same-day 14:00 edge cases (inclusive deadline, just after reject)

## 3. Customer meal-off service and API

- [x] 3.1 Implement `customer_meal_off(delivery, user, note="")` with ownership, scheduled-only, deadline, skip_source=customer, and order completion hook
- [x] 3.2 Add `POST /orders/{id}/deliveries/{delivery_id}/meal-off` for verified customer owners
- [x] 3.3 Enrich delivery serializers with `can_meal_off`, `meal_off_deadline_at`, `skip_source`
- [x] 3.4 OpenAPI examples for meal-off success and deadline/ownership errors

## 4. Admin settings API

- [x] 4.1 Add GET/PATCH meal-off settings endpoint for verified admins (serializer + IANA timezone validation)
- [x] 4.2 Wire admin URLs (web and/or shared admin path consistent with order admin)
- [x] 4.3 Tests: defaults on first load, update dinner time, non-admin forbidden, invalid timezone

## 5. Documentation

- [x] 5.1 Backend docs: deadlines, endpoint, skip_source vs admin mark, no-refund note
- [x] 5.2 Frontend docs: when to show Meal Off button, deadline display, error states

## 6. Verification

- [x] 6.1 Tests: successful lunch/dinner meal-off, late reject, other-user 404/403, daily package completes after meal-off
- [x] 6.2 Smoke: create monthly order → meal-off tomorrow’s lunch before deadline → slot skipped on detail/today board
