## ADDED Requirements

### Requirement: Successful customer recharge credits Admin Wallet custody
When a customer wallet recharge completes successfully, the system SHALL credit the Admin Wallet by the same amount as a completed `customer_funding` transaction. The credit MUST use direction `credit`, MUST link the related customer profile and customer wallet transaction when available, and MUST run in the same database transaction as the customer credit when practical.

#### Scenario: Customer recharge increases Admin Wallet balance
- **WHEN** a verified customer successfully recharges `500.00` into their personal wallet
- **THEN** the Admin Wallet balance increases by `500.00` and exactly one completed `customer_funding` credit of `500.00` exists for that customer wallet transaction

#### Scenario: Failed customer recharge does not credit Admin Wallet
- **WHEN** a recharge attempt is rejected (invalid amount, frozen wallet, or funding disabled)
- **THEN** no Admin Wallet `customer_funding` credit is created for that attempt

### Requirement: Successful customer withdraw debits Admin Wallet custody
When a customer wallet withdraw completes successfully, the system SHALL debit the Admin Wallet by the same amount as a completed `customer_withdraw` transaction (direction `debit`), linked to the customer wallet transaction. If the Admin Wallet balance is insufficient for that debit, the system MUST reject the customer withdraw without changing the customer wallet balance.

#### Scenario: Customer withdraw decreases Admin Wallet balance
- **WHEN** a verified customer successfully withdraws `100.00` and the Admin Wallet balance is at least `100.00`
- **THEN** the Admin Wallet balance decreases by `100.00` and exactly one completed `customer_withdraw` debit of `100.00` exists for that customer wallet transaction

#### Scenario: Insufficient Admin Wallet float blocks customer withdraw
- **WHEN** a customer requests a withdraw of `100.00` but the Admin Wallet balance is less than `100.00`
- **THEN** the system rejects the withdraw, the customer wallet balance is unchanged, and no Admin Wallet debit is created

### Requirement: Funding custody credits are idempotent
The system MUST ensure at most one successful Admin Wallet `customer_funding` credit per customer recharge wallet transaction and at most one successful Admin Wallet `customer_withdraw` debit per customer withdraw wallet transaction. Retries and concurrent requests MUST NOT double-apply custody movements.

#### Scenario: Replayed recharge idempotency key does not double-credit Admin Wallet
- **WHEN** a customer recharge succeeds with an idempotency key and the same request is replayed
- **THEN** the customer wallet and Admin Wallet are each credited only once for that funding event

#### Scenario: Replayed withdraw does not double-debit Admin Wallet
- **WHEN** a customer withdraw succeeds and the same idempotent withdraw is replayed
- **THEN** the customer wallet and Admin Wallet are each debited only once for that withdraw event

### Requirement: Funding custody can be reconciled
The system SHALL provide a management command that can detect completed customer recharge/withdraw transactions missing matching Admin Wallet custody rows and backfill them idempotently (with a dry-run mode).

#### Scenario: Dry-run reports missing funding credits
- **WHEN** an operator runs the funding reconcile command in dry-run mode and a completed customer recharge has no Admin Wallet `customer_funding` row
- **THEN** the command reports the missing credit without writing ledger rows
