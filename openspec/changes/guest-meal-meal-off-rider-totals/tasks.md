# Tasks

## 1. WP-01/02 — Personal Meal-OFF eligibility gate

- [x] 1.1 Add `is_personal_meal_off` (or equivalent) helper using `OrderDelivery` `skipped` + `skip_source=customer` for `(subscription/customer, service_date, meal_period)` and call it from `build_guest_meal_quote`; verify unit tests cover lunch/dinner independence and that admin/system skips alone do not trigger `PERSONAL_MEAL_OFF`
- [x] 1.2 Raise `GuestMealNotEligibleError` with `code=PERSONAL_MEAL_OFF` and the agreed message on preview/create; verify API tests return HTTP 422 with `error_code=PERSONAL_MEAL_OFF` and no wallet/quota side effects
- [x] 1.3 In `create_guest_meal_order`, lock the target delivery with `select_for_update(of=('self',))`, revalidate personal Meal-OFF + scheduled status after locks and before debit; verify a test where Meal-OFF happens between preview and create rejects create without debit
- [x] 1.4 Update OpenAPI examples on guest-meal views for the new error and verify schema generation still includes Guest Meals tag responses

## 2. WP-03 — Delivery linking and Meal-OFF ↔ Guest interaction

- [x] 2.1 Change create so unresolved delivery after `ensure_subscription_deliveries` fails before debit (no successful `delivery=null`); verify tests assert rejection and zero wallet transactions
- [x] 2.2 In `customer_meal_off` (and `can_meal_off`), block when scheduled Guest Meals exist for the same slot; verify Meal-OFF API rejects, delivery stays scheduled, and Guest Meal unchanged
- [x] 2.3 Confirm `sync_guest_meals_for_delivered_delivery` + `charge_delivered_meal` still do not re-charge guest totals; verify existing guest deliver integration test (or new assertion) still passes
- [x] 2.4 Document orphan/legacy null-delivery handling in backend guest-meal notes and verify the doc states reject-at-create (no silent cancel/refund)

## 3. WP-04 — Rider board quantity totals

- [x] 3.1 Add `total_meal_quantity = meal_quantity + guest_quantity` on deliveryman board rows in `delivery_zones/services/board.py` without changing regular/guest semantics; verify board tests for 2+3=5, 5+0=5, and multi-GuestMealOrder aggregation
- [x] 3.2 Mirror the same additive total on admin today-board serializers if they expose guest quantity; verify serializer/API test includes the new field
- [x] 3.3 Update `delivery_zones/docs/frontend/deliveryman-today-ops.md` (and related board docs) with example JSON including `total_meal_quantity`; verify examples match implementation

## 4. WP-05 — Rider today-summary box metrics

- [x] 4.1 Extend `build_deliveryman_today_summary` with regular/guest/total and delivered/pending **meal box** metrics using the same zone/date/period/low-balance scope as the board; verify summary totals reconcile with board box sums under the same filters
- [x] 4.2 Keep existing stop-count fields (`total`/`delivered`/`pending`) unchanged; verify a compatibility assertion that those keys remain present with stop semantics
- [x] 4.3 Update OpenAPI/docs for today-summary new fields and verify documented field meanings distinguish stop counts vs box counts

## 5. WP-06 — Wallet / idempotency hardening (no policy change)

- [x] 5.1 Add/extend regression tests proving Meal-OFF rejection and delivery-unavailable rejection create no wallet rows and leave monthly quota unchanged
- [x] 5.2 Re-run/extend idempotency tests: same key+payload replay, same key+different payload → 409, concurrent quota ceiling; verify no double debit
- [x] 5.3 Document observed recharge-floor vs commission_first debit behavior in backend guest-meal docs without changing formulas unless a confirmed bug is found; verify doc notes match `debit_wallet` defaults

## 6. WP-07/08 — Integration regression matrix and documentation sweep

- [x] 6.1 Expand `orders/tests/test_guest_meal.py` (and meal-off tests) for the full eligibility matrix in the proposal (ON/OFF combinations, non-subscriber, expired/inactive sub, past date, cutoff, missing price); verify the suite passes
- [x] 6.2 Add delivery_zones tests for scheduled/delivered board + summary reconciliation with guest quantities; verify cancelled guests are excluded
- [x] 6.3 Rewrite contradictory Meal-OFF allowance text in `orders/docs/GUEST_MEAL_INTEGRATION_GUIDE.md`, `orders/docs/backend/guest-meal-order.md`, frontend guest-meal docs, and any meal-off docs that claim guest can be bought while OFF; verify docs mention `PERSONAL_MEAL_OFF` and Meal-OFF blocked-when-guest
- [x] 6.4 Run focused test modules (`orders.tests.test_guest_meal`, meal-off tests, deliveryman board/summary tests) and verify all pass before marking the change ready for review

## Workflow follow-up

- After implementation approval and merge criteria are met, archive this change and sync specs into `openspec/specs/` (guest-meal capabilities were never archived from `guest-meal-order-system`).
- Do not reopen completed change `guest-meal-order-system`; treat this change as the superseding Meal-OFF / rider-totals contract.
