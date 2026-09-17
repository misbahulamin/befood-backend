## 1. Service wiring

- [x] 1.1 In `wallet/services/funding.py` `reject_withdraw`, after reservation credit + wallet save, call `maybe_resume_after_wallet_credit(wallet.customer)` and set transient `locked_txn.meal_service_restored`
- [x] 1.2 Confirm resume runs inside the existing `@transaction.atomic` (same pattern as `approve_recharge`); do not change `approve_withdraw` or `reject_recharge` resume behavior

## 2. Admin API contract

- [x] 2.1 In `wallet/api/web_views.py` reject action, pass `meal_service_restored` from withdraw reject into `AdminFundingRequestSerializer` context (default `false` for recharge reject)
- [x] 2.2 Update OpenAPI / extend_schema description on reject so withdraw reject may return `meal_service_restored=true`
- [x] 2.3 Confirm serializer already exposes `meal_service_restored` via context/`getattr` (no schema migration)

## 3. Tests

- [x] 3.1 Add service test: pending withdraw drops balance → meal block → reject restores above threshold → flags cleared and `meal_service_restored=True`
- [x] 3.2 Add service test: reject restores but still below threshold → block remains and `meal_service_restored=False`
- [x] 3.3 Add API test: admin withdraw reject `200` includes correct `meal_service_restored`; recharge reject stays `false`
- [x] 3.4 Keep/extend existing withdraw-approve tests asserting no meal restore on approve

## 4. Docs

- [x] 4.1 Update `wallet/docs/frontend/manual-wallet-funding.md` meal-restore section to include withdraw reject (not only recharge approve)
- [x] 4.2 Update backend funding notes if they claim reject never restores meal service

## 5. Verification

- [x] 5.1 Run focused tests (`test_meal_service_resume_on_approve` + any new withdraw-reject cases) and fix failures
