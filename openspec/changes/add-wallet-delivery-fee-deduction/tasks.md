## 1. Model and ledger foundations

- [x] 1.1 Add `WalletTransaction.Type.DELIVERY_FEE_PAYMENT = 'delivery_fee_payment'` and extend `debit_wallet` debit strategy mapping to use `commission_first` (same as `payment`)
- [x] 1.2 Add `DeliveryFeePayment` model in `wallet` with `public_id`, customer FK, amount, `payment_month`/`payment_year`, status, `deducted_by_admin`, OneToOne/FK to `WalletTransaction`, `reason`, `source` (manual/automatic), nullable automation fields (`fee_rule_code`, service-area/metadata), timestamps
- [x] 1.3 Add unique constraint for one paid payment per `(customer, payment_year, payment_month)` plus indexes for reporting filters
- [x] 1.4 Generate/review migration; register read-friendly Django admin for `DeliveryFeePayment`

## 2. Deduct service and notifications

- [x] 2.1 Implement `wallet/services/delivery_fee.py` `charge_delivery_fee(...)` with atomic `select_for_update`, amount/wallet-status validation, month uniqueness, idempotency key, `debit_wallet`, payment row create, `reviewed_by`/`reviewed_at` on txn
- [x] 2.2 Ensure Admin Wallet cash is not mutated by delivery-fee deduct; call `evaluate_meal_stop_after_debit` after successful debit
- [x] 2.3 Implement `wallet/services/delivery_fee_notifications.py` (inbox + FCM, `on_commit`, type `delivery_fee_deducted`, screen `wallet`) mirroring funding/meal notification reliability
- [x] 2.4 Wire notification after successful `charge_delivery_fee` without failing the money path on notify errors

## 3. Admin deduct and customer context APIs

- [x] 3.1 Add web URL module for delivery fees and mount under `/api/v1/web/delivery-fees/` plus customer-nested routes under `/api/v1/web/customers/{public_id}/`
- [x] 3.2 Implement `GET .../customers/{public_id}/delivery-fee-context/` (name, phone, wallet balances, active subscription, fee history summary) with `IsVerifiedAdmin`
- [x] 3.3 Implement `POST .../customers/{public_id}/delivery-fee-payments/` deduct endpoint (`amount`, `payment_month`, `payment_year`, `reason`, `Idempotency-Key`) returning `201` on success
- [x] 3.4 Implement `GET .../customers/{public_id}/delivery-fee-payments/` paginated customer history
- [x] 3.5 Reject insufficient balance with clear error; reject frozen wallet; reject duplicate month with `409` (idempotent replay safe)
- [x] 3.6 Add serializers + OpenAPI helpers/examples for context, deduct, and list

## 4. Reporting APIs

- [x] 4.1 Implement `GET /api/v1/web/delivery-fees/reports/monthly/?year=&month=` with collected amount, paid customer count, pending active-subscriber count
- [x] 4.2 Implement `GET /api/v1/web/delivery-fees/reports/lifetime/` with lifetime collected amount and distinct paid customers
- [x] 4.3 Implement optional `GET /api/v1/web/delivery-fees/payments/` global list with allowlisted filters (year, month, customer, status, q)
- [x] 4.4 Enforce verified-admin auth on all report/list endpoints; document unsupported filter → `400`

## 5. Customer wallet history contract

- [x] 5.1 Extend customer `WalletTransactionSerializer` to expose a delivery-fee context block for `type=delivery_fee_payment` (billing month/year, amount, processed-by signal)
- [x] 5.2 Ensure meal-payment serializer path stays gated to meal purpose only and does not treat delivery-fee rows as meals
- [x] 5.3 Update customer wallet OpenAPI schema for the new fields

## 6. Documentation

- [x] 6.1 Add `wallet/docs/frontend/delivery-fee-deduction.md` covering select → amount → confirm, errors, history, report widgets, meal vs fee history
- [x] 6.2 Add `wallet/docs/backend/delivery-fee-deduction.md` covering model, service flow, custody note, reversal design, notification type, pending-customer definition
- [x] 6.3 Cross-link from existing wallet/admin customer frontend docs where admins already manage customers/wallets

## 7. Tests

- [x] 7.1 Service tests: successful deduct creates payment + `delivery_fee_payment` debit; insufficient/frozen rejected; duplicate month rejected; idempotent key replay safe
- [x] 7.2 API permission tests: verified admin allowed; customer/unauthenticated denied
- [x] 7.3 Reporting tests: monthly collected/paid/pending; lifetime totals; empty month behavior
- [x] 7.4 Notification tests: inbox created on success; debit remains if FCM fails
- [x] 7.5 Customer wallet history tests: delivery-fee context present; meal payment unchanged
- [x] 7.6 Regression: meal delivery charge path still creates meal payment (not delivery-fee type); Admin Wallet cash unchanged on fee deduct
- [x] 7.7 Run targeted wallet/user_management/notifications test suites and fix failures
