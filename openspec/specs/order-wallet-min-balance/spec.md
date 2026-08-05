# Order Wallet Minimum Balance Eligibility

## Purpose
Require a usable, sufficiently funded customer wallet before creating a meal package order.

## Requirements

### Requirement: Order create requires minimum wallet balance

Before creating a meal package order for a verified customer, the system SHALL require that the customer’s wallet `balance` is greater than or equal to the configured `min_wallet_balance_to_order`. The check MUST run after same-month package lock passes. Passing this check MUST NOT debit the wallet or create a wallet payment transaction.

#### Scenario: Balance at or above minimum allows order

- **WHEN** a verified customer has no locking order for the target month, an active wallet with balance `500.00`, and the configured minimum is `500.00`, and they create a meal package order
- **THEN** the system creates the order successfully and the wallet balance remains `500.00`

#### Scenario: Balance below minimum rejects order

- **WHEN** a verified customer has wallet balance `499.99` and the configured minimum is `500.00` and they attempt to create a meal package order
- **THEN** the system rejects the request with a validation error about insufficient wallet balance and does not create an order

#### Scenario: Missing wallet is treated as zero balance

- **WHEN** a verified customer has no wallet row and the configured minimum is greater than zero and they attempt to create a meal package order
- **THEN** the system rejects the request for insufficient wallet balance and does not create an order

### Requirement: Frozen wallet cannot place an order

The system MUST reject meal package order creation when the customer’s wallet status is `frozen`, even if the numeric balance meets the minimum.

#### Scenario: Frozen wallet with sufficient balance is rejected

- **WHEN** a verified customer has wallet status `frozen`, balance `1000.00`, and the configured minimum is `500.00`, and they attempt to create a meal package order
- **THEN** the system rejects the request and does not create an order

### Requirement: Month lock is evaluated before wallet balance

When both a same-month locking order and an insufficient wallet would fail, the system MUST surface the month-lock failure first. The system MUST NOT create an order in either failure case.

#### Scenario: Existing month package fails before wallet messaging

- **WHEN** a verified customer already has a non-cancelled package for the target month and also has wallet balance below the minimum
- **THEN** the system rejects the request with the month-lock error and does not create an order
