## 1. Audit confirmation

- [x] 1.1 Re-read `auto_meal_delivery.eligible_delivery_queryset` / `run_auto_delivery` and `DeliverymanMarkDeliveryView` and record the shared vs divergent checklist in a short code comment or backend doc section (matches design Context table)
- [x] 1.2 Confirm admin mark path is separate and must remain able to mark low-balance blocked customers

## 2. Shared eligibility helper

- [x] 2.1 Extract or reuse a single low-balance meal-stop exclude predicate/Q (prefer existing `meal_demand` helper) usable by auto-delivery queryset and deliveryman mark
- [x] 2.2 Refactor `eligible_delivery_queryset` to call that shared helper (behavior-preserving)

## 3. Deliveryman mark gate

- [x] 3.1 In `DeliverymanMarkDeliveryView` (or a thin service called from it), reject mark when customer is meal-stop blocked, before `mark_delivery_and_notify`
- [x] 3.2 Map rejection to HTTP `422` with stable `error_code` (e.g. `MEAL_SERVICE_BLOCKED_LOW_BALANCE`); keep zone `403` and wallet errors unchanged
- [x] 3.3 Ensure admin mark APIs are untouched by this gate

## 4. Tests

- [x] 4.1 Add deliveryman test: blocked low-balance customer → mark rejected, status unchanged, no debit
- [x] 4.2 Add deliveryman test: unblocked eligible zone delivery → mark succeeds via shared path
- [x] 4.3 Add/extend test: rider mark then auto-delivery does not double charge (if not already covered for this setup)
- [x] 4.4 Add assertion that admin can still mark a blocked customer’s delivery

## 5. Docs

- [x] 5.1 Update `delivery_zones/docs/frontend/zone-based-delivery.md` — mark eligibility + error code for meal-stop block
- [x] 5.2 Update `delivery_zones/docs/backend/zone-based-delivery.md` — parity with auto-delivery + admin override
- [x] 5.3 Update `orders/docs/backend/auto-meal-delivery.md` — note deliveryman mark shares completion path and low-balance exclusion
