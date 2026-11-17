# Tasks

## 1. Settings and data model

- [x] 1.1 Add `OrderWalletSettings.test_meal_box_price` (default `10.00`) and `test_meal_lifetime_quota` (default `2`) with migration; extend order-wallet-settings service/serializers/admin PATCH and verify settings GET/PATCH round-trip in a focused test
- [x] 1.2 Add `TestMealOrder` model (`PublicIdMixin`) with customer, package, service_date, meal_period, special_instructions, price snapshots, currency, address FK + snapshots, delivery window snapshots, order/payment statuses, payment fields, timestamps, cancellation fields, source_channel, idempotency_key unique per customer; register in Django admin minimally; verify migration applies
- [x] 1.3 Add `TestMealPaymentEvent` (or equivalent audit model) and `TestMealFunnelEvent` with dedupe constraints; verify migrations apply
- [x] 1.4 Add nullable `OrderDelivery.test_meal_order` FK + indexes and document parent exclusivity rules in model help_text; verify migration applies without breaking existing subscription/order deliveries

## 2. Domain services (eligibility, quote, create)

- [x] 2.1 Implement eligibility service using `get_active_subscription`, lifetime quota count, and reason codes/messages (Bengali quota exhausted string); verify unit tests for eligible, active subscriber, quota exhausted, unauthenticated handled at API layer
- [x] 2.2 Implement package listing for active + subscribable `MealCategory` and slot validation for date/period via published menu helpers; verify inactive/unpublished packages excluded
- [x] 2.3 Implement quote: `resolve_published_slot` + box charge + delivery windows + cutoff/`business_today` checks with Decimal money; verify lunch/dinner pricing and past-date/cutoff rejects
- [x] 2.4 Implement atomic `create_test_meal_order`: lock/quota, revalidate quote, address ownership + serviceability, persist order + `OrderDelivery` stop, no wallet debit, Idempotency-Key replay/conflict; verify create success leaves wallet unchanged and concurrent creates cannot exceed quota
- [x] 2.5 Implement safe order_status transitions and mark-delivered hook that updates Test Meal without `charge_delivered_meal`; verify delivered+unpaid coexistence and cancelled rows excluded from countable cooking set

## 3. Customer APIs

- [x] 3.1 Add serializers/views for `GET eligibility/`, `GET packages/`, `POST quote/`, `POST orders/`, `GET orders/`, `GET orders/{public_id}/` under `/api/v1/test-meals/`; mount URLs; verify OpenAPI annotations generate
- [x] 3.2 Map domain errors to project error shape (`401`/`403`/`404`/`409`/`422`) including `ACTIVE_SUBSCRIBER`, `QUOTA_EXHAUSTED`, cutoff/price/address errors; verify API tests for auth isolation and other-customer address/order denial
- [x] 3.3 Add optional `POST funnel-events/` with dedupe; verify duplicate event counted once and click-only traffic does not create orders

## 4. Admin payment, list, analytics

- [x] 4.1 Implement admin record-payment + correction with audit events; verify non-admin denied, paid does not change fulfillment status, duplicate record does not double-count collected revenue
- [x] 4.2 Implement admin list/detail with pagination, search, and filters (date, package, period, order/payment status, zone, conversion); verify filter/search API tests
- [x] 4.3 Implement conversion analytics service (primary after-delivery KPI, pre-delivery subscribe split, historical conversion after cancel) and `GET analytics/` chart series; verify empty-denominator safe rate and conversion scenarios from specs
- [x] 4.4 Document revenue splits (confirmed vs collected vs outstanding vs delivered-unpaid) in admin serializer/docs and verify analytics fields match fixtures

## 5. Ops integration

- [x] 5.1 Extend `meal_demand.get_demand` (and admin statistics) to include countable Test Meal units by package without double-counting guest/subscription; verify demand tests cover add/exclude cancelled
- [x] 5.2 Extend deliveryman/admin board and today-summary with `test_meal_quantity` (and total formula); verify board tests show Test Meal separately from guest/regular
- [x] 5.3 Update admin dashboard meals-served to add `test_meals_served` and consolidated total = regular + guest + test; verify dashboard unit test; confirm guest/subscription charge paths untouched
- [x] 5.4 Ensure kitchen today-meal-requirement uses shared demand including Test Meals; verify kitchen count/ingredient scaling test with one Test Meal present

## 6. Documentation

- [x] 6.1 Write `orders/docs/backend/test-meal-order.md` covering settings, models, customer/admin endpoints, quota/payment/cutoff/conversion rules, status transitions, and verification steps
- [x] 6.2 Write `orders/docs/frontend/test-meal-order.md` for Flutter (eligibility → packages → quote → address → create → history) with example JSON and error handling
- [x] 6.3 Write `orders/docs/frontend/admin-test-meals.md` for Admin Panel (list/filters/payment/analytics/conversion) matching shipped admin APIs

## 7. Test suite completion and regression

- [x] 7.1 Complete remaining automated cases from the product checklist (timezone boundaries, price change between quote and confirm, unpublished menu, concurrent quota, conversion variants, funnel dedupe, revenue reconciliation) in `orders/tests/test_test_meal*.py` (and related demand/board tests)
- [x] 7.2 Run focused Test Meal + guest meal + meal demand + board regression suites and fix failures; record pass/fail summary for the implementation report

## Workflow follow-up

- After implementation review, run `/opsx-apply` was already used for build; archive with `/opsx-archive` when accepted.
- Flutter and React Admin Panel implementation are separate follow-on work outside this backend change.
- Decide later whether manual collected payments should post into `admin_wallet` cash/profit ledgers.
