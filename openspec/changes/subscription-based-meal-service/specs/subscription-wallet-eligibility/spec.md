## ADDED Requirements

### Requirement: Subscribe requires minimum wallet balance

Before creating an active subscription for a verified customer, the system SHALL require that the customer’s wallet `balance` is greater than or equal to the configured `min_wallet_balance_to_order`. Passing this check MUST NOT debit the wallet or create a wallet payment transaction. The check MUST run after the one-active-subscription exclusivity check.

#### Scenario: Balance at or above minimum allows subscribe

- **WHEN** a verified customer has no active subscription, an active wallet with balance `500.00`, and the configured minimum is `500.00`, and they subscribe to an available plan
- **THEN** the system creates the subscription successfully and the wallet balance remains `500.00`

#### Scenario: Balance below minimum rejects subscribe

- **WHEN** a verified customer has wallet balance `499.99` and the configured minimum is `500.00` and they attempt to subscribe
- **THEN** the system rejects the request with a validation error about insufficient wallet balance and does not create a subscription

#### Scenario: Missing wallet is treated as zero balance

- **WHEN** a verified customer has no wallet row and the configured minimum is greater than zero and they attempt to subscribe
- **THEN** the system rejects the request for insufficient wallet balance and does not create a subscription

### Requirement: Frozen wallet cannot subscribe

The system MUST reject subscribe when the customer’s wallet status is `frozen`, even if the numeric balance meets the minimum.

#### Scenario: Frozen wallet with sufficient balance is rejected

- **WHEN** a verified customer has wallet status `frozen`, balance `1000.00`, and the configured minimum is `500.00`, and they attempt to subscribe
- **THEN** the system rejects the request and does not create a subscription

### Requirement: Active subscription exclusivity is evaluated before wallet balance

When both an existing active subscription and an insufficient wallet would fail, the system MUST surface the already-subscribed failure first. The system MUST NOT create a subscription in either failure case.

#### Scenario: Existing active subscription fails before wallet messaging

- **WHEN** a verified customer already has an active subscription and also has wallet balance below the minimum
- **THEN** the system rejects the request with the already-subscribed error and does not create a subscription
