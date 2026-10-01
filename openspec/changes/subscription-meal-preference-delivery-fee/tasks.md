## 1. Backend foundation

- [x] 1.1 Confirm/finish `CustomerSubscription.quantity` model field + additive migration `0019` (default `1`, no snapshot rewrite)
- [x] 1.2 Implement `wallet/services/subscription_delivery_fee.py` (`normalize_quantity`, `calculate_subscription_delivery_fee`, `format_fee_summary`) with tiers lunch/dinner=200; both 1-3=400, 4-5=350, 6+=300
- [x] 1.3 Complete `normalize_meal_preference` / `resolve_effective_meal_period` / `normalize_subscription_quantity` in `subscribe_customer` (fallback when preference omitted)
- [x] 1.4 Ensure `ensure_subscription_deliveries` only uses `periods_for_meal_period(subscription.meal_period_snapshot)` (already true - add regression tests)

## 2. Backend API & admin

- [x] 2.1 Finalize `SubscribeSerializer` + create response fields (`meal_period_snapshot`, `quantity`, `monthly_delivery_fee`, `fee_rule_code`)
- [x] 2.2 Finalize `POST /api/v1/subscriptions/quote/` (`SubscriptionQuoteSerializer` + view action)
- [x] 2.3 Expose fee/quantity on customer current/detail and admin subscription serializers
- [x] 2.4 Update `build_active_subscription_payload` to include quantity + calculated fee without breaking admin 360
- [x] 2.5 Update OpenAPI examples and `orders/docs/backend/customer-meal-subscription.md` (+ frontend doc notes)

## 3. Backend tests

- [x] 3.1 Preference scheduling tests: lunch-only / dinner-only / both create correct periods
- [x] 3.2 Legacy omit-preference falls back to package period; existing both rows keep both on ensure
- [x] 3.3 Fee calculator unit tests including boundaries 3 and 4; invalid quantity
- [x] 3.4 Quote API: success, invalid preference, no wallet debit, no subscription created
- [x] 3.5 Compatibility: meal OFF/ON, cancel classification, meal payment unchanged for preference cases

## 4. Web frontend (`befood-frontend`)

- [ ] 4.1 Extend types + `subscriptionsApi` for `meal_preference`, `quantity`, quote endpoint, response fee fields
- [ ] 4.2 Add quote TanStack Query hook; never hardcode fee amounts
- [ ] 4.3 Update `SubscribeConfirmModal` UX: preference cards, quantity when both, live fee from quote, review + confirm
- [ ] 4.4 Wire `useSubscribe` payload; loading/error/double-submit guards; map new validation errors
- [ ] 4.5 Admin Customer 360: display preference, quantity, monthly fee on active-subscription tab (read-only)

## 5. Mobile (`befood_mobile`)

- [ ] 5.1 Extend DTOs/models/service: subscribe + quote payloads/responses
- [ ] 5.2 Update `SubscribeConfirmCubit`/`State` for preference, quantity, quoted fee
- [ ] 5.3 Update `SubscribeConfirmPage` UI (platform-appropriate selection + review); double-tap protection
- [ ] 5.4 Cubit/widget tests for selection required, fee refresh, error mapping

## 6. Deploy & verification

- [x] 6.1 Staging smoke checklist documented in backend docs (migrate, subscribe variants, quote, meal-off, cancel)
- [x] 6.2 Document production deploy order: backend (compat on) then web then mobile store
- [x] 6.3 Confirm admin manual delivery-fee deduct still works; calculator amount available for operators
- [x] 6.4 Document rollback: reverse quantity migration if needed; revert code keeps existing snapshots intact
