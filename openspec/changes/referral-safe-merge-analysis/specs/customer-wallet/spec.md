## MODIFIED Requirements

### Requirement: Customer has exactly one wallet with public identity
The system SHALL ensure each `CustomerProfile` has at most one wallet. The wallet MUST expose opaque `public_id` (UUID) as the client identity and MUST NOT require clients to use the integer primary key. The wallet MUST store `balance` as a non-negative decimal with two fractional digits representing total spendable funds, plus `recharge_balance` and `commission_balance` such that `balance == recharge_balance + commission_balance` at all times after dual-bucket migration. The wallet MUST store `currency` (default `BDT`) and `status` of `active` or `frozen`. Accessing the caller’s wallet when none exists MUST create an active wallet with all balances `0`. Customer wallet summary responses MUST expose `recharge_balance`, `commission_balance`, and `withdrawable_balance` (equal to `recharge_balance`) in addition to total `balance`.

#### Scenario: First wallet access creates zero balance
- **WHEN** an authenticated verified customer requests their wallet and no wallet row exists yet
- **THEN** the system creates an active wallet with `balance`, `recharge_balance`, and `commission_balance` all `0.00`, currency `BDT`, and returns it with `public_id`

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
The system SHALL record every completed balance change as an append-only `WalletTransaction` and MUST update `Wallet.balance` and the corresponding bucket fields only through the ledger service path. Completed transaction monetary fields MUST NOT be editable via the customer API. Concurrent updates MUST NOT allow the total balance or either bucket to become negative. Completed credits and debits MUST persist `balance_after`, `recharge_balance_after`, and `commission_balance_after` such that `balance_after == recharge_balance_after + commission_balance_after`. Referral commission credits MUST increase `commission_balance`. Customer recharge credits MUST increase `recharge_balance`. Meal payment debits MUST consume `commission_balance` before `recharge_balance` when both are available.

#### Scenario: Credit increases balance and writes ledger row
- **WHEN** the ledger service credits a wallet by a positive amount into the appropriate bucket
- **THEN** a credit transaction is stored with total and bucket after-balances equal to the new wallet state and the wallet balances increase accordingly

#### Scenario: Debit decreases balance and writes ledger row
- **WHEN** the ledger service debits a wallet by a positive amount not exceeding the current total balance under the applicable strategy
- **THEN** a debit transaction is stored with consistent after-balance snapshots and the wallet balances decrease accordingly

#### Scenario: Debit rejected when insufficient funds
- **WHEN** the ledger service attempts to debit more than the funds available for the chosen strategy
- **THEN** the system rejects the operation without changing balances and without creating a completed debit that would overdraw

#### Scenario: Meal payment consumes commission first
- **WHEN** a meal payment debit of `30.00` is applied to a wallet with `commission_balance` `20.00` and `recharge_balance` `50.00`
- **THEN** resulting balances are `commission_balance` `0.00`, `recharge_balance` `40.00`, and `balance` `40.00`
