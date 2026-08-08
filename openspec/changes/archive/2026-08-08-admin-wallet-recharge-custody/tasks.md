## 1. Model & settings

- [x] 1.1 Add Admin Wallet transaction types `customer_funding` (credit) and `customer_withdraw` (debit); update `CREDIT_TYPES` / `DEBIT_TYPES` allowlists
- [x] 1.2 Add lifetime counters on `AdminWallet` for customer funding (and withdraws if needed) + migration
- [x] 1.3 Add settings flag `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED` (default `True`) and document meal cash-credit flag deprecation/disable

## 2. Funding custody ingestion

- [x] 2.1 Implement `credit_from_customer_recharge(customer_txn)` with idempotency key `customer-recharge:{txn.public_id}`
- [x] 2.2 Implement `debit_from_customer_withdraw(customer_txn)` with idempotency key `customer-withdraw:{txn.public_id}` and insufficient-float error
- [x] 2.3 Hook both into `recharge_wallet` / `withdraw_wallet` in the same atomic block (lazy import); map float shortfall to API error
- [x] 2.4 Update ledger lifetime counter application for the new types

## 3. Meal payment accounting change

- [x] 3.1 Remove or no-op cash `credit_from_meal_payment` call from `charge_delivered_meal` so meal charges do not increase Admin Wallet balance
- [x] 3.2 Update dashboard/summary meal-revenue (`total_customer_payments` / period metrics) to use charged meal payments or delivery aggregates, not funding credits
- [x] 3.3 Ensure type filters still expose `customer_funding` / `customer_withdraw` / historical `customer_payment` rows correctly

## 4. Reconcile tooling

- [x] 4.1 Add `reconcile_admin_wallet_customer_funding` management command with `--dry-run`
- [x] 4.2 Document interaction with existing `reconcile_admin_wallet_meal_payments` and cutover warnings about old meal cash credits

## 5. Tests

- [x] 5.1 Replace/invert `test_customer_recharge_does_not_credit_admin_wallet`; add recharge credit + withdraw debit + idempotency tests
- [x] 5.2 Add test that insufficient Admin Wallet float rejects customer withdraw without customer balance change
- [x] 5.3 Update meal-charge Admin Wallet tests to assert no cash credit / no double-count after prior recharge
- [x] 5.4 Add/adjust API tests if withdraw error mapping or new summary fields are exposed

## 6. Docs & OpenAPI

- [x] 6.1 Update `admin_wallet/docs/backend/admin-wallet.md` (custody vs meal revenue, flags, reconcile)
- [x] 6.2 Update `admin_wallet/docs/frontend/admin-wallet.md` (card meanings, new types, filters)
- [x] 6.3 Cross-link `wallet/docs/backend/customer-wallet.md` for Admin Wallet side effects on recharge/withdraw
- [x] 6.4 Refresh OpenAPI descriptions for Admin Wallet summary/dashboard field semantics if counters change
