## ADDED Requirements

### Requirement: Wallet exposes recharge and commission balance buckets
The system SHALL store customer wallet funds in two non-negative buckets: `recharge_balance` (withdrawable) and `commission_balance` (meal-spendable, not withdrawable). The existing `balance` field MUST equal `recharge_balance + commission_balance` and remain the total spendable amount for meal payments and balance thresholds. Wallet summary API responses MUST include `balance`, `recharge_balance`, `commission_balance`, and `withdrawable_balance` (equal to `recharge_balance`).

#### Scenario: Wallet summary includes bucket fields
- **WHEN** an authenticated verified customer requests their wallet after migration
- **THEN** the system responds `200` with `balance`, `recharge_balance`, `commission_balance`, and `withdrawable_balance`

#### Scenario: Existing balance migrates to recharge bucket
- **WHEN** a wallet with legacy `balance` `250.00` is migrated
- **THEN** `recharge_balance` is `250.00`, `commission_balance` is `0.00`, and `balance` remains `250.00`

### Requirement: Wallet migration validates bucket consistency for all wallets
The dual-bucket data migration MUST set `recharge_balance = balance` and `commission_balance = 0` for existing wallets and MUST verify that every wallet satisfies `balance == recharge_balance + commission_balance` before the migration is considered complete. The system SHALL provide a management command `verify_wallet_balance_consistency` that scans all wallets and fails non-zero when any wallet violates the invariant.

#### Scenario: Post-migration invariant holds for all wallets
- **WHEN** the dual-bucket migration finishes
- **THEN** every wallet row satisfies `balance == recharge_balance + commission_balance`

#### Scenario: Consistency command detects drift
- **WHEN** an operator runs `verify_wallet_balance_consistency` and at least one wallet violates the invariant
- **THEN** the command exits non-zero and reports the offending wallet identities

### Requirement: Ledger updates maintain bucket invariant
The system SHALL update wallet buckets only through the ledger service under row locking. Completed credits and debits MUST keep `balance == recharge_balance + commission_balance` with no negative buckets. Referral commission credits MUST increase `commission_balance`. Customer recharge credits MUST increase `recharge_balance`. Meal payment debits MUST reduce total `balance` without allowing overdraft and MUST consume `commission_balance` before `recharge_balance` when both are available.

#### Scenario: Referral commission credit updates commission bucket
- **WHEN** the ledger credits `10.00` as `referral_commission`
- **THEN** `commission_balance` and `balance` increase by `10.00` and `recharge_balance` is unchanged

#### Scenario: Meal payment prefers commission bucket
- **WHEN** a wallet has `commission_balance` `3.00` and `recharge_balance` `10.00` and a meal payment debits `5.00`
- **THEN** `commission_balance` becomes `0.00`, `recharge_balance` becomes `8.00`, and `balance` becomes `8.00`

### Requirement: Completed wallet transactions store total and bucket after-balances
Every completed customer wallet ledger transaction MUST persist `balance_after`, `recharge_balance_after`, and `commission_balance_after` such that `balance_after == recharge_balance_after + commission_balance_after`. Pending transactions that do not finalize a balance change MAY leave after-balance fields null until completion, consistent with existing pending funding behavior.

#### Scenario: Completed credit stores consistent after snapshots
- **WHEN** a completed credit increases commission balance by `5.00` on a wallet that previously had total `20.00` all in recharge
- **THEN** the transaction stores `recharge_balance_after` `20.00`, `commission_balance_after` `5.00`, and `balance_after` `25.00`

#### Scenario: Completed meal debit stores consistent after snapshots
- **WHEN** a completed meal payment debit finishes
- **THEN** the payment transaction’s after-balance fields sum to `balance_after` and match the wallet buckets

## MODIFIED Requirements

### Requirement: Customer has exactly one wallet with public identity
The system SHALL ensure each `CustomerProfile` has at most one wallet. The wallet MUST expose opaque `public_id` (UUID) as the client identity and MUST NOT require clients to use the integer primary key. The wallet MUST store `balance` as a non-negative decimal with two fractional digits equal to `recharge_balance + commission_balance`, `currency` (default `BDT`), and `status` of `active` or `frozen`. Accessing the caller’s wallet when none exists MUST create an active wallet with `balance` `0`, `recharge_balance` `0`, and `commission_balance` `0`.

#### Scenario: First wallet access creates zero balance
- **WHEN** an authenticated verified customer requests their wallet and no wallet row exists yet
- **THEN** the system creates an active wallet with balance `0.00`, recharge and commission balances `0.00`, currency `BDT`, and returns it with `public_id`

#### Scenario: Wallet summary for existing wallet
- **WHEN** an authenticated verified customer with an existing wallet requests their wallet
- **THEN** the system responds `200` with `public_id`, `balance`, `recharge_balance`, `commission_balance`, `withdrawable_balance`, `currency`, and `status`

#### Scenario: Unauthenticated wallet access rejected
- **WHEN** an unauthenticated client requests the wallet
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Customer cannot read another customer wallet
- **WHEN** an authenticated verified customer calls the wallet endpoint
- **THEN** the system returns only that caller’s wallet and does not accept another customer’s identifier as authorization to view a different wallet

### Requirement: Ledger is the source of truth for balance changes
The system SHALL record every completed balance change as an append-only `WalletTransaction` and MUST update `Wallet.balance` and the corresponding bucket fields only through the ledger service path. Completed transaction monetary fields MUST NOT be editable via the customer API. Concurrent updates MUST NOT allow the total balance or either bucket to become negative. Completed rows MUST include consistent total and bucket after-balance snapshots.

#### Scenario: Credit increases balance and writes ledger row
- **WHEN** the ledger service credits a wallet by a positive amount into the appropriate bucket
- **THEN** a credit transaction is stored with `balance_after` equal to the new total balance and matching bucket after fields, and the wallet total balance increases by that amount

#### Scenario: Debit decreases balance and writes ledger row
- **WHEN** the ledger service debits a wallet by a positive amount not exceeding the current total balance
- **THEN** a debit transaction is stored with `balance_after` equal to the new total balance and matching bucket after fields, and the wallet total balance decreases by that amount

#### Scenario: Debit rejected when insufficient funds
- **WHEN** the ledger service attempts to debit more than the current total balance
- **THEN** the system rejects the operation without changing balances and without creating a completed debit that would overdraw
