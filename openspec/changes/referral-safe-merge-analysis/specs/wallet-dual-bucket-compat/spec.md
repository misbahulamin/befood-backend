## ADDED Requirements

### Requirement: Dual buckets coexist with live provider-ref uniqueness
The customer wallet MUST expose dual buckets (`recharge_balance`, `commission_balance`) with denormalized total `balance` while retaining the production UniqueConstraint on provider recharge `(method, external_ref)` limited to live statuses `pending` and `completed`.

#### Scenario: Model has buckets and live-status constraint
- **WHEN** the integrated `Wallet` / `WalletTransaction` models are inspected
- **THEN** bucket fields exist and `wallet_txn_unique_provider_recharge_ref` includes the live-status condition from production-hotfix

### Requirement: Dual-bucket data migration is safe on existing balances
When dual buckets are first applied, every existing wallet MUST set `recharge_balance = balance` and `commission_balance = 0`, and the migration MUST fail if any wallet violates `balance == recharge_balance + commission_balance`.

#### Scenario: Existing balance becomes recharge bucket
- **WHEN** a wallet with balance `150.00` is migrated to dual buckets
- **THEN** `recharge_balance` is `150.00`, `commission_balance` is `0.00`, and total `balance` remains `150.00`

#### Scenario: Drift fails migration
- **WHEN** a wallet would violate the bucket invariant during migration
- **THEN** the migration aborts without leaving inconsistent production wallets half-applied

### Requirement: Verification commands remain available
The integrated codebase MUST keep both production `audit_wallet_accounting` and dual-bucket `verify_wallet_balance_consistency` management commands.

#### Scenario: Both commands exist
- **WHEN** operators inspect wallet management commands after integration
- **THEN** both `audit_wallet_accounting` and `verify_wallet_balance_consistency` are available
