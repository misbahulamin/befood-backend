## Why

Customer withdrawals can leave meal service unprotected because withdrawable amount ignores `meal_stop_threshold`, and operators often misread Admin Wallet custody because `total_customer_funding` is a lifetime inflow counter that never decreases on withdraw—even though platform cash already moves via `customer_withdraw`. We need a production-safe rule that caps withdrawals at `recharge_balance - meal_stop_threshold`, clarifies/hardens Admin Wallet custody sync on approve, and exposes the calculated maximum to mobile, customer web, and admin clients.

## What Changes

- Cap customer withdraw requests so amount cannot exceed `max(0, recharge_balance - meal_stop_threshold)` (commission balance remains non-withdrawable).
- Update wallet summary contract so `withdrawable_balance` / `maximum_withdrawable` reflects that formula (not full `recharge_balance`).
- Harden and document withdraw-approve Admin Wallet sync: keep debit type `customer_withdraw` (do **not** reverse/edit historical `customer_funding` credit rows); ensure approve path always posts the custody debit atomically with withdraw completion.
- Add admin-facing clarity for net customer custody (`total_customer_funding - total_customer_withdrawals`) so panels stop expecting `total_customer_funding` itself to shrink on withdraw.
- Re-validate remaining balance vs threshold on admin approve for **new** requests; do not rewrite historical ledger rows or recalculate live balances.
- Update backend + frontend docs for mobile withdraw UI, customer web wallet, and admin approve summary.
- **BREAKING** (additive semantics): `withdrawable_balance` meaning changes from “full recharge_balance” to “recharge_balance minus meal_stop_threshold (floored at 0)”. Clients that treated it as full recharge must use the new value or read `recharge_balance` explicitly.

## Capabilities

### New Capabilities

- `wallet-withdraw-meal-stop-guard`: Withdraw amount limits and API exposure of maximum withdrawable based on recharge bucket + `meal_stop_threshold`.
- `wallet-withdraw-client-docs`: Mobile, customer web, and admin panel documentation for the updated withdraw UX and validation messages.

### Modified Capabilities

- `wallet-funding`: Withdraw request validation uses recharge-only + meal-stop floor; approve remains atomic with Admin Wallet custody debit.
- `customer-wallet`: Wallet summary exposes threshold-aware withdrawable amount (and related display fields).
- `admin-wallet-funding-custody`: Clarify that withdraw custody out is `customer_withdraw` (not a mutation of `customer_funding` credit rows); optional net-custody reporting for operators.
- `admin-wallet-frontend-docs`: Admin UI must show withdraw remaining-balance / threshold context and net custody correctly.

## Impact

- Backend: `wallet/services/funding.py`, `wallet/models.py`, `wallet/api/serializers.py`, `wallet/api/views.py` / `web_views.py`, tests under `wallet/tests/`; Admin Wallet path `admin_wallet/services/ingestion.py` + dashboard/summary serializers if net custody field is added.
- Settings source: existing `OrderWalletSettings.meal_stop_threshold` via `orders/services/order_wallet_settings.py` (no new settings model).
- APIs: customer wallet GET / withdraw POST; admin funding approve; optional admin wallet summary field.
- Clients: mobile withdraw screen, customer web wallet, admin withdraw approve panel (docs only in this repo).
- Production: forward-only behavior; no historical transaction rewrite; reconcile command remains available for missing custody rows only.
