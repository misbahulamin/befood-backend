## ADDED Requirements

### Requirement: Platform has exactly one Admin Wallet
The system SHALL maintain a single BeFood platform Admin Wallet with opaque `public_id`, currency default `BDT`, non-negative `balance` with two fractional digits, and `status` of `active` or `frozen`. The wallet MUST represent the central business cash ledger, not a per-admin personal balance. Accessing Admin Wallet APIs when the singleton row is missing MUST create or seed the platform wallet with balance `0.00`.

#### Scenario: First access seeds zero-balance platform wallet
- **WHEN** a verified admin requests the Admin Wallet and no platform wallet row exists
- **THEN** the system creates an active platform wallet with balance `0.00`, currency `BDT`, and returns it with `public_id`

#### Scenario: Subsequent access returns the same wallet
- **WHEN** a verified admin requests the Admin Wallet after it was seeded
- **THEN** the system returns the same singleton wallet identity and current balance

### Requirement: Ledger is the source of truth for Admin Wallet balance
The system SHALL record every completed balance change as an append-only Admin Wallet transaction and MUST update `balance` only through the ledger service path. Each completed transaction MUST store positive `amount`, `direction` (`credit` or `debit`), `type`, `status`, `balance_after`, and timestamps. Concurrent updates MUST NOT allow the balance to become negative. Completed monetary fields MUST NOT be editable via API.

#### Scenario: Credit increases balance and writes ledger row
- **WHEN** the ledger service credits the Admin Wallet by a positive amount
- **THEN** a completed credit transaction is stored with `balance_after` equal to the new balance and the wallet balance increases by that amount

#### Scenario: Debit decreases balance and writes ledger row
- **WHEN** the ledger service debits the Admin Wallet by a positive amount not exceeding available balance
- **THEN** a completed debit transaction is stored with `balance_after` equal to the new balance and the wallet balance decreases by that amount

#### Scenario: Overdraft debit is rejected
- **WHEN** a debit is attempted for an amount greater than the current balance
- **THEN** the system rejects the operation, does not create a completed debit, and leaves the balance unchanged

### Requirement: Idempotent ledger writes prevent duplicate movements
The system SHALL accept an idempotency key for automated and retried ledger writes and MUST enforce uniqueness of that key per Admin Wallet. Replaying the same key with the same logical operation MUST return the original completed transaction without changing the balance again.

#### Scenario: Replay of the same idempotency key does not double credit
- **WHEN** a credit is posted with idempotency key `K` and the same credit is posted again with `K`
- **THEN** only one completed credit exists for `K` and the balance increased only once

### Requirement: Balance is reconcilable from the ledger
The system MUST ensure that for completed transactions, the Admin Wallet balance equals the sum of completed credits minus the sum of completed debits (starting from zero at wallet creation), within normal decimal precision.

#### Scenario: Ledger sum matches denormalized balance
- **WHEN** an Admin Wallet has a series of completed credits and debits
- **THEN** recomputing balance from those completed ledger rows matches the stored wallet balance
