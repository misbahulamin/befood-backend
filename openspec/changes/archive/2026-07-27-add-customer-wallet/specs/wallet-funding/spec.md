## ADDED Requirements

### Requirement: Customer can recharge wallet with manual funding
The system SHALL allow an authenticated verified customer to recharge their wallet by posting a positive monetary `amount`. For this release, successful recharge MUST credit the wallet immediately, create a completed ledger transaction with `type=recharge`, `direction=credit`, and `method=manual`, and return the updated wallet balance together with the transaction `public_id`. The system MUST reject non-positive amounts, amounts with more than two decimal places, and amounts above the configured maximum. The customer MUST NOT supply a payment gateway method in this release; the server sets `manual`.

#### Scenario: Successful manual recharge
- **WHEN** an authenticated verified customer with an active wallet posts a valid recharge amount (for example `500.00`)
- **THEN** the system responds with success, the wallet balance increases by that amount, and a completed `recharge` transaction with `method=manual` exists

#### Scenario: Invalid recharge amount rejected
- **WHEN** a customer posts a recharge with amount `0`, a negative value, or more than two decimal places
- **THEN** the system responds `400` or `422` and does not change the wallet balance

#### Scenario: Frozen wallet cannot recharge
- **WHEN** a customer whose wallet `status` is `frozen` posts a recharge
- **THEN** the system rejects the operation and does not credit the balance

#### Scenario: Unauthenticated recharge rejected
- **WHEN** an unauthenticated client posts a recharge
- **THEN** the system responds `401 Unauthorized`

### Requirement: Customer can withdraw from wallet with manual debit
The system SHALL allow an authenticated verified customer to withdraw by posting a positive monetary `amount` not exceeding the current balance. For this release, successful withdraw MUST debit the wallet immediately, create a completed ledger transaction with `type=withdraw`, `direction=debit`, and `method=manual`, and return the updated balance together with the transaction `public_id`. Insufficient funds MUST be rejected without changing the balance. Frozen wallets MUST reject withdraw.

#### Scenario: Successful manual withdraw
- **WHEN** an authenticated verified customer with balance at least `500.00` posts a withdraw of `500.00`
- **THEN** the system responds with success, the wallet balance decreases by `500.00`, and a completed `withdraw` transaction with `method=manual` exists

#### Scenario: Withdraw exceeds balance
- **WHEN** a customer posts a withdraw amount greater than the current balance
- **THEN** the system rejects the operation and the balance remains unchanged

#### Scenario: Frozen wallet cannot withdraw
- **WHEN** a customer whose wallet `status` is `frozen` posts a withdraw
- **THEN** the system rejects the operation and does not debit the balance

### Requirement: Funding operations support idempotent retries
The system SHALL accept an optional idempotency key on recharge and withdraw. When the same customer reuses the same key with the same effective funding request, the system MUST return the original successful result without applying the balance change twice. When the same key is reused with a different amount, the system MUST respond `409 Conflict`.

#### Scenario: Replay same idempotency key does not double credit
- **WHEN** a customer successfully recharges with an idempotency key and then retries the same recharge with the same key and amount
- **THEN** the system returns the original transaction outcome and the wallet is credited only once

#### Scenario: Idempotency key reused with different amount
- **WHEN** a customer reuses an idempotency key for a funding request with a different amount
- **THEN** the system responds `409 Conflict` and does not apply an additional balance change

### Requirement: Funding model is gateway-ready without live gateway integration
The system SHALL persist `method` and `status` on funding transactions so future bKash/Nagad (and similar) flows can create pending transactions and complete them after provider confirmation. This release MUST NOT claim a live gateway payment succeeded and MUST NOT require gateway credentials. Reserved method values MUST include at least `manual`, `bkash`, and `nagad`.

#### Scenario: Manual path completes without gateway
- **WHEN** a customer completes recharge or withdraw in this release
- **THEN** the transaction `method` is `manual` and `status` is `completed` without calling an external payment provider

#### Scenario: Schema reserves gateway methods
- **WHEN** wallet funding transactions are stored
- **THEN** the `method` field allows `bkash` and `nagad` as reserved values for future integration even though customer APIs do not select them yet
