## Why

Customers need a trusted balance to pay for meals and receive refunds later, but the `wallet` app is still an empty stub (no models, ledger, or mounted APIs). We need a professional wallet foundation now—manual recharge and withdraw first—so bKash/Nagad gateway funding can plug in later without redesigning balances or transaction history.

## What Changes

- Implement the `wallet` domain: one wallet per `CustomerProfile`, immutable ledger entries, and service-layer credit/debit with concurrency-safe balance updates.
- Add authenticated customer APIs to view wallet balance, list transactions, recharge (manual credit for now), and withdraw (manual debit for now).
- Design funding operations with explicit source/method and status fields so future gateway recharge (bKash, Nagad) and payout withdraw can attach without breaking the ledger contract.
- Enforce UUID-first public identity (`public_id`) on exposed wallet resources before mounting routes (per deferred-domain UUID convention).
- Register Django admin for wallet and ledger inspection; mount wallet URLs under the project API tree.
- Add tests and backend/frontend docs covering auth, ownership, validation, insufficient balance, and ledger integrity.
- **Out of scope for this change:** live bKash/Nagad/SSLCommerz integration, order checkout paying from wallet, admin manual adjustments UI beyond Django admin, multi-currency.

## Capabilities

### New Capabilities
- `customer-wallet`: Authenticated customer owns exactly one wallet; can view balance/status and paginated transaction history via public UUID identity.
- `wallet-funding`: Customer can recharge (credit) and withdraw (debit) with validated amounts; current path is immediate manual funding, structured for future gateway confirmation.

### Modified Capabilities
- (none)

## Impact

- **App:** `wallet/` (models, migrations, services, API, admin, tests, docs) — currently empty stubs.
- **URLs:** New mount in `core/urls.py` (e.g. `/wallet/` alongside existing domain prefixes).
- **Auth:** Token auth + `HasCustomerProfile` (customer-scoped); no cross-customer access.
- **Related (not changed now):** `payments` remains the future gateway home; order `payment_method` / wallet checkout stays deferred.
- **Clients:** Mobile/web customer apps can show balance, history, recharge, and withdraw screens.
- **Docs/tests:** New coverage under `wallet/docs/` and `wallet/tests/`.
