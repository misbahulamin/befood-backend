## Why

Admins expect that when a customer recharges their personal wallet, BeFood’s Admin Wallet balance increases—but today it does not. Investigation shows this is not a broken hook: `admin-wallet-system` v1 **intentionally** credits Admin Wallet only on successful meal-delivery charges (`credit_from_meal_payment`), and explicitly forbids recharge credits to avoid double-counting. That product choice conflicts with ops’ mental model of “cash entered the platform,” so Admin Wallet looks empty/wrong after recharges until meals are delivered.

## What Changes

- Treat successful **customer wallet recharge** as platform **cash custody**: auto-credit Admin Wallet by the same amount (idempotent, linked to the customer wallet transaction).
- Treat successful **customer wallet withdraw** as cash leaving custody: auto-debit Admin Wallet by the same amount when balance allows (idempotent); define failure policy if Admin Wallet is short.
- **Stop auto-crediting Admin Wallet cash balance on meal-delivery payment** so recharge + later meal charge cannot double-count the same taka. Meal charges remain customer-wallet debits and keep order/delivery payment history.
- Expose meal-delivery charges as **revenue recognition / liability release** for dashboard metrics (without a second cash credit), so “customer payments / meal revenue” cards stay meaningful.
- Add reconcile tooling for historical recharges/withdraws (and optional cleanup guidance for any meal-payment cash credits already posted under the old model).
- Update Admin Wallet backend/frontend docs and reverse the v1 test/spec that asserted “recharge leaves Admin Wallet unchanged.”
- **BREAKING (accounting semantics):** Admin Wallet balance timing moves from “credit when meal delivered” to “credit when customer funds wallet”; existing dashboards/docs that assumed meal-time cash credit must be updated. Historical balances may need reconcile/cutover.

## Capabilities

### New Capabilities
- `admin-wallet-funding-custody`: Idempotent Admin Wallet credit on customer recharge and debit on customer withdraw, with source tracking to the customer wallet transaction and customer profile.
- `admin-wallet-meal-revenue-recognition`: Meal-delivery wallet charges no longer cash-credit Admin Wallet; they record recognized meal revenue / release prepaid liability for reporting without double-counting cash.

### Modified Capabilities
- `wallet-funding`: Successful manual recharge/withdraw MUST trigger the Admin Wallet custody side effects (same atomic block when practical) in addition to existing customer-ledger behavior.
- `meal-delivery-wallet-payment`: Clarify that successful meal charge updates Admin Wallet revenue recognition only (not a cash credit), and MUST NOT increase Admin Wallet balance a second time for prepaid funds.

## Impact

- **Apps:** `admin_wallet/` (models types/counters, `services/ingestion.py`, ledger counters, queries/dashboard aggregates, reconcile command, tests, docs); `wallet/services/ledger.py` (hooks after `recharge_wallet` / `withdraw_wallet`); `orders/services/meal_payment.py` (replace/repurpose `_credit_admin_wallet_for_meal`).
- **APIs:** Admin Wallet summary/dashboard field meanings (`total_customer_payments`, today/month income) may change composition; document clearly. Customer `/wallet/recharge/` and `/wallet/withdraw/` response shapes stay compatible.
- **Settings:** New feature flags (e.g. `ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED`) and revisit `ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED` semantics.
- **Data:** Optional backfill of past recharges; decide cutover for prior `customer_payment` cash credits already in ledger.
- **Related change:** Builds on completed `openspec/changes/admin-wallet-system/` (not yet archived into main specs).
