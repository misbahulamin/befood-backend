## 1. Order reopen helper

- [x] 1.1 Add a service helper to reopen a `completed` order after meal-on (`completed` → `active`, or `confirmed` when no deliveries are `delivered` yet) with status history note
- [x] 1.2 Restrict reopen to internal meal-on use (not a public customer status API)

## 2. Meal-on service

- [x] 2.1 Implement `can_meal_on(delivery, now=...)` using customer-skipped + same deadline helpers as meal-off
- [x] 2.2 Implement `customer_meal_on(delivery, user, note="")` with ownership, skip_source=customer, deadline gate, restore `scheduled`, clear skip markers, and call reopen helper when needed
- [x] 2.3 Ensure meal-on creates no wallet debit and does not call mark-delivered payment paths

## 3. Customer API and serializers

- [x] 3.1 Add `POST .../deliveries/{delivery_id}/meal-on` on the customer order viewset mirroring meal-off auth/ownership
- [x] 3.2 Add request serializer (optional note) and OpenAPI for meal-on
- [x] 3.3 Enrich delivery serializers with `can_meal_on` (keep `can_meal_off` / `meal_off_deadline_at`)

## 4. Tests

- [x] 4.1 Unit/API tests: meal-on success before dinner/lunch deadline; reject after deadline; leave status unchanged
- [x] 4.2 Tests: toggle off→on before deadline; reject meal-on for admin skip and other customer's delivery
- [x] 4.3 Tests: daily package completes after meal-off then reopens after meal-on; serializer eligibility flags
- [x] 4.4 Tests: meal-on does not debit wallet; later mark delivered after meal-on charges once

## 5. Docs

- [x] 5.1 Update backend/frontend customer meal-off docs for meal-on endpoint, deadline lock for Off/On, default-on vs off (no delivery / no charge), and reopen behavior
- [x] 5.2 Note in meal-off settings docs that configured times gate both Off and On
