## 1. Audit and shared withdrawable helper

- [x] 1.1 Confirm `approve_withdraw` → `_sync_admin_wallet_withdraw` → `debit_from_customer_withdraw` path and document any production flag/`customer_withdraw` gaps in backend notes (no historical rewrite)
- [x] 1.2 Add shared helper / update `Wallet.withdrawable_balance` to `max(0, recharge_balance - meal_stop_threshold)` using `get_order_wallet_settings()`
- [x] 1.3 Keep debit strategy recharge-only; ensure commission cannot be withdrawn

## 2. Withdraw validation and API contract

- [x] 2.1 Enforce meal-stop-aware maximum in `request_withdraw` before reservation with clear client-facing error
- [x] 2.2 Update `WalletSerializer.get_withdrawable_balance` (and OpenAPI helpers) to match the new formula; keep `meal_stop_threshold` on wallet summary
- [x] 2.3 Ensure admin funding approve remains atomic with Admin Wallet `customer_withdraw` debit; do not mutate `customer_funding` credit rows

## 3. Admin Wallet net custody reporting

- [x] 3.1 Expose derived `net_customer_funding` (`total_customer_funding - total_customer_withdrawals`) on Admin Wallet summary and/or dashboard serializers
- [x] 3.2 Confirm lifetime `total_customer_funding` is unchanged on withdraw approve while `balance` and `total_customer_withdrawals` update

## 4. Tests

- [x] 4.1 Add/update wallet funding tests for max withdrawable formula, over-limit reject, zero-headroom reject, and commission ignored
- [x] 4.2 Add/update tests that approve creates `customer_withdraw` debit, does not reduce `total_customer_funding`, and rolls back approve on Admin float shortfall
- [x] 4.3 Add/update Admin Wallet API tests for `net_customer_funding` (or equivalent) and wallet GET `withdrawable_balance` semantics

## 5. Documentation

- [x] 5.1 Update `wallet/docs/backend/customer-wallet.md` and `wallet/docs/frontend/manual-wallet-funding.md` for meal-stop withdraw rule and field meanings
- [x] 5.2 Update `admin_wallet/docs/frontend/admin-wallet.md` and backend admin-wallet docs for `customer_withdraw` vs `total_customer_funding` and net custody
- [x] 5.3 Document admin withdraw-approve UI expectations (balance before, amount, remaining, meal-stop) for panel engineers

## 6. Verification

- [x] 6.1 Run targeted wallet and admin_wallet tests related to funding/withdraw/dashboard
- [x] 6.2 Smoke-check: withdraw request over limit fails; under limit reserves; approve debits Admin Wallet balance via `customer_withdraw`
