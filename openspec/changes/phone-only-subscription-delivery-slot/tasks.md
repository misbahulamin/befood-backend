## 1. Backend audit confirmation

- [ ] 1.1 Re-verify subscribe → `ensure_subscription_deliveries` call chain and document exact files/functions in a short AUDIT note under the change (or backend docs) confirming no email gate on slot creation
- [ ] 1.2 Grep and list all remaining `is_email_verified=True` / email-required checks in orders meal/subscription/ops paths; classify create-path vs ops-path
- [ ] 1.3 Confirm published-menu skip behavior in `ensure_subscription_deliveries` and how ops should interpret ACTIVE + zero slots

## 2. Identity and ops parity fixes

- [ ] 2.1 Replace email-only filter in `orders/services/wallet_balance_thresholds.py` `candidate_customers_queryset` with identity-verified rule (phone or email or social)
- [ ] 2.2 Replace email-only filter in `orders/services/meal_close.py` `slot_low_balance_deliveries` with the same identity rule
- [ ] 2.3 Prefer a shared queryset/helper for identity-verified customers to avoid drift
- [ ] 2.4 Confirm `SubscribeSerializer` / `IsVerifiedCustomer` already use `is_customer_identity_verified`; fix only if a gap remains

## 3. Delivery slot generation hardening

- [ ] 3.1 Add/extend regression test: phone-only customer + published menu → subscribe creates OrderDelivery rows
- [ ] 3.2 Add test: phone-only + unpublished menu → ACTIVE subscription with zero slots (documented behavior)
- [ ] 3.3 Add test: email added after slots exist → ensure does not duplicate slots
- [ ] 3.4 Optionally add structured log when ensure creates zero rows due to unpublished menus (no behavior change)

## 4. Read-only missing-slot audit

- [ ] 4.1 Implement management command (read-only) reporting ACTIVE subscriptions with zero OrderDelivery counts
- [ ] 4.2 Include phone-only cohort breakdown and unpublished-menu vs published-menu classification
- [ ] 4.3 Document how to remediate safely: publish menus + run existing `ensure_subscription_deliveries` (no data migration)

## 5. Docs, mobile, and admin review

- [ ] 5.1 Fix stale doc claim that unverified email → 403 on subscribe (`orders/docs/frontend/customer-meal-subscription.md` and related)
- [ ] 5.2 Document phone-only validity and slot/menu relationship in backend referral/subscription docs as needed
- [ ] 5.3 Mobile impact note: verify registration/subscribe responses; DO NOT make email mandatory; optional address-complete warning only
- [ ] 5.4 Admin impact note: blank email is valid; optional registration-method display as follow-up (out of scope unless trivial)

## 6. Verification

- [ ] 6.1 Run targeted orders/user_management tests for subscribe, wallet thresholds, meal-close, and new audit command help/dry-run
- [ ] 6.2 Manual checklist: Scenario 1 email register+subscribe; Scenario 2 phone-only+subscribe+slots; Scenario 3 email later no dupes
- [ ] 6.3 Production-safe rollout checklist: deploy filters/tests → run read-only audit → publish menus if needed → ensure-all → sample verify
