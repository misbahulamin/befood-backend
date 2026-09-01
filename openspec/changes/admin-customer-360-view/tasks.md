## 1. Confirmation gate

- [x] 1.1 Review updated OpenSpec artifacts with stakeholder and confirm Phase 2 backend work may start
- [x] 1.2 Confirm resolved decisions in `design.md` (legacy collapsible section, wallet pending inline, deprecated alias timeline)

## 2. Backend — subscription-first service layer

- [x] 2.1 Add `build_active_subscription_payload()` using `orders.services.subscription_service.get_active_subscription`
- [x] 2.2 Add `customer_subscriptions_queryset()` with delivered/skipped annotations for history list
- [x] 2.3 Refactor `customer_deliveries_queryset()` to filter `Q(order__customer=…) | Q(subscription__customer=…)`
- [x] 2.4 Update `build_overview_metrics()` with subscription-aware counts, CLV, `last_payment_at`, `last_meal_delivered_at`, `current_package_expires_at`, wallet totals
- [x] 2.5 Refactor `build_activity_events()` to confirmed-event allowlist only (no `updated_at` inference)
- [x] 2.6 Add `build_wallet_overview()` with `available_balance`, `pending_recharge_amount`, `pending_withdraw_amount`, `total_recharged`, `total_withdrawn`, `total_spent`
- [x] 2.7 Add list filters: `has_active_subscription`, `has_wallet`, `has_pending_recharge`, `subscription_expiring_soon`, `inactive_subscription`; keep `has_active_order` as deprecated alias

## 3. Backend — API serializers and views

- [x] 3.1 Add serializers: active subscription, subscription history (status from model choices), wallet overview, compact wallet summary
- [x] 3.2 Refactor `AdminCustomerDetailSerializer` to lean overview: profile + summary + active_subscription summary + wallet_summary only (no history arrays)
- [x] 3.3 Add ViewSet actions: `active_subscription`, `subscriptions`, `wallet_overview`
- [x] 3.4 Mark `active_order` and `orders` deprecated with `Deprecation` response headers
- [x] 3.5 Update OpenAPI schemas for new/changed admin customer endpoints

## 4. Backend — tests and docs

- [x] 4.1 Test: detail overview excludes history arrays (no subscriptions/meals/wallet/activity lists embedded)
- [x] 4.2 Test: subscribed customer returns non-null active subscription on detail and active-subscription action
- [x] 4.3 Test: meal/meal-off history includes subscription-linked `OrderDelivery` rows
- [x] 4.4 Test: overview metrics and wallet overview aggregates match ledger/subscription data
- [x] 4.5 Test: wallet overview shows `pending_recharge_amount` for pending manual funding
- [x] 4.6 Test: activity feed emits only confirmed events; no spurious events from generic `updated_at`
- [x] 4.7 Test: object-level isolation — Customer A token cannot read Customer B detail or any nested sub-resource → 403
- [x] 4.8 Test: auth (401 unauthenticated), pagination, unknown `public_id` (404), deprecated alias headers
- [x] 4.9 Test: list filters (`has_wallet`, `has_pending_recharge`, `has_active_subscription`, etc.)
- [x] 4.10 Update `user_management/docs/backend/admin-customer-management.md` for subscription-first lean overview contracts

## 5. Frontend — API contract alignment (`befood-frontend`)

- [x] 5.1 Update `customerManagementTypes.ts` to backend field names and new summary/wallet fields
- [x] 5.2 Add API functions and React Query hooks for `active-subscription`, `subscriptions`, `wallet-overview`
- [x] 5.3 Ensure overview hook loads only detail endpoint; history hooks lazy-enabled per tab
- [x] 5.4 Render subscription `status` from API value (tolerate unknown enums)
- [x] 5.5 Remove or deprecate hooks calling `active-order` and `orders` for primary tabs

## 6. Frontend — Customer 360 UI redesign

- [x] 6.1 Rename tabs: Active Subscription, Subscription History; remove Active order / Order history labels
- [x] 6.2 Add header summary cards: active subscription, wallet balance, meals delivered, total subscriptions, CLV, last payment, last meal, package expiry
- [x] 6.3 Implement Active Subscription tab with empty state "No active subscription"
- [x] 6.4 Implement Subscription History tab with pagination
- [x] 6.5 Implement Wallet Overview tab with pending recharge/withdraw + totals (support scenario)
- [x] 6.6 Add collapsible "Legacy monthly orders" section — visible only when customer has legacy Order rows; loads `/orders/` on expand
- [x] 6.7 Fix Overview tab: full profile fields, addresses (`full_address`), allergy fields
- [x] 6.8 Verify Meal History, Meal-offs, Wallet History, Activity tabs after backend subscription-aware update
- [x] 6.9 Add loading skeletons and empty states for all tabs per existing Admin Panel patterns

## 7. Frontend docs and QA

- [x] 7.1 Update `user_management/docs/frontend/admin-customer-management.md` for subscription-first tabs, lazy load, legacy section rule
- [ ] 7.2 Manual QA: Customer A scenario in staging
- [ ] 7.3 Manual QA: Customer B scenario in staging
- [ ] 7.4 Manual QA: Customer C scenario in staging
- [ ] 7.5 Manual QA: Customer D scenario in staging
- [x] 7.6 QA: Customer A token cannot access Customer B admin pages (403) — covered by automated tests

## 8. Post-implementation report (after apply)

- [x] 8.1 Document changed files, removed components, API changes, and test results per stakeholder checklist
