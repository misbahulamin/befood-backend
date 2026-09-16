## MODIFIED Requirements

### Requirement: Successful customer recharge credits Admin Wallet custody
When a customer wallet recharge is approved and becomes completed, the system SHALL credit the Admin Wallet by the same amount as a completed `customer_funding` transaction. The credit MUST use direction `credit`, MUST link the related customer profile and customer wallet transaction when available, and MUST run in the same database transaction as the customer credit when practical. Creating a pending customer recharge MUST NOT create an Admin Wallet `customer_funding` credit.

#### Scenario: Approved customer recharge increases Admin Wallet balance
- **WHEN** a verified admin approves a pending customer recharge of `500.00`
- **THEN** the Admin Wallet balance increases by `500.00` and exactly one completed `customer_funding` credit of `500.00` exists for that customer wallet transaction

#### Scenario: Pending customer recharge does not credit Admin Wallet
- **WHEN** a customer submits a pending recharge of `500.00`
- **THEN** no Admin Wallet `customer_funding` credit is created for that pending transaction

#### Scenario: Failed or rejected customer recharge does not credit Admin Wallet
- **WHEN** a recharge request is rejected by an admin or a submit attempt fails validation
- **THEN** no Admin Wallet `customer_funding` credit is created for that attempt

### Requirement: Successful customer withdraw debits Admin Wallet custody
When a customer wallet withdraw is approved and becomes completed, the system SHALL debit the Admin Wallet by the same amount as a completed `customer_withdraw` transaction (direction `debit`), linked to the customer wallet transaction. Creating a pending customer withdraw MUST NOT debit Admin Wallet custody. If the Admin Wallet balance is insufficient for that debit at approve time, the system MUST respond `409 Conflict`, MUST leave the customer withdraw `pending` with reservation intact, MUST create no Admin Wallet debit, and MUST leave funding review audit fields unchanged. Rejecting a pending withdraw MUST NOT debit Admin Wallet custody. The system MUST NOT auto-reject the withdraw solely due to float shortfall.

#### Scenario: Approved customer withdraw decreases Admin Wallet balance
- **WHEN** a verified admin approves a pending customer withdraw of `100.00` and the Admin Wallet balance is at least `100.00`
- **THEN** the Admin Wallet balance decreases by `100.00` and exactly one completed `customer_withdraw` debit of `100.00` exists for that customer wallet transaction

#### Scenario: Pending customer withdraw does not debit Admin Wallet
- **WHEN** a customer submits a pending withdraw of `100.00`
- **THEN** no Admin Wallet `customer_withdraw` debit is created yet

#### Scenario: Insufficient Admin Wallet float blocks approve without mutation
- **WHEN** an admin attempts to approve a pending withdraw of `100.00` but the Admin Wallet balance is less than `100.00`
- **THEN** the system responds `409 Conflict`, the customer withdraw remains pending with reservation intact, no Admin Wallet debit is created, and `reviewed_by`, `reviewed_at`, and `rejection_reason` remain unchanged

### Requirement: Funding custody credits are idempotent
The system MUST ensure at most one successful Admin Wallet `customer_funding` credit per customer recharge wallet transaction and at most one successful Admin Wallet `customer_withdraw` debit per customer withdraw wallet transaction. Retries, duplicate approve attempts, and concurrent requests MUST NOT double-apply custody movements. A second approve against an already-completed funding request MUST return `409 Conflict` without applying another custody movement.

#### Scenario: Second approve does not double-credit Admin Wallet
- **WHEN** a pending recharge is approved and a second approve is attempted for the same transaction
- **THEN** the system responds `409 Conflict` and the Admin Wallet is credited only once for that funding event

#### Scenario: Second approve does not double-debit Admin Wallet
- **WHEN** a pending withdraw is approved and a second approve is attempted for the same transaction
- **THEN** the system responds `409 Conflict` and the Admin Wallet is debited only once for that withdraw event
