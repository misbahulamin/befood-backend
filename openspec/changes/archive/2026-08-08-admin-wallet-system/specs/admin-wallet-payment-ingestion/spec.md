## ADDED Requirements

### Requirement: Successful meal-delivery payment credits Admin Wallet
When a customer meal-delivery wallet charge completes successfully, the system SHALL credit the Admin Wallet by the same charged amount as a completed `customer_payment` transaction. The credit MUST use direction `credit` and MUST record payment method indicating customer wallet (for example `wallet`).

#### Scenario: Delivered meal charge credits Admin Wallet
- **WHEN** an authorized operator marks a delivery `delivered` and the customer wallet is successfully debited `62.00`
- **THEN** the Admin Wallet balance increases by `62.00` and a completed `customer_payment` credit of `62.00` exists for that payment

#### Scenario: Failed customer charge does not credit Admin Wallet
- **WHEN** mark-delivered fails because the customer wallet has insufficient balance
- **THEN** no Admin Wallet `customer_payment` credit is created for that delivery attempt

### Requirement: Payment source tracking is machine-readable
Each automatic Admin Wallet payment credit MUST include source tracking sufficient for admin history: transaction type, amount, credit direction, source/reference labels, related order identifier when available, related delivery identifier when available, customer identifier when available, payment method, note, timestamps, and status.

#### Scenario: History shows order and delivery context
- **WHEN** a meal-delivery payment credits the Admin Wallet
- **THEN** the Admin Wallet transaction exposes order and delivery references plus customer context so an admin can identify which payment produced the credit

### Requirement: Duplicate payment credits are prevented
The system MUST ensure at most one successful Admin Wallet credit exists per meal-delivery payment (keyed by delivery and/or an equivalent idempotency key). Retries, concurrent mark-delivered requests, or reconcile backfills MUST NOT credit the Admin Wallet twice for the same delivery payment.

#### Scenario: Retry after successful charge does not double credit Admin Wallet
- **WHEN** a delivery was already charged and Admin Wallet credited, and mark-delivered is posted again
- **THEN** Admin Wallet balance is unchanged by the retry and only one completed `customer_payment` credit exists for that delivery payment

### Requirement: Customer wallet recharge is not Admin Wallet income in v1
The system MUST NOT automatically credit the Admin Wallet when a customer performs a wallet recharge. Recharge remains a customer-wallet liability movement unless a future capability explicitly defines custody accounting.

#### Scenario: Customer recharge leaves Admin Wallet unchanged
- **WHEN** a verified customer successfully recharges their personal wallet
- **THEN** the Admin Wallet balance and ledger gain no automatic credit from that recharge
