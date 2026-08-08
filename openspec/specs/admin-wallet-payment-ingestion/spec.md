## Purpose

Historical / emergency Admin Wallet meal-payment cash ingestion rules. Under custody accounting (`admin-wallet-funding-custody` + `admin-wallet-meal-revenue-recognition`), meal charges MUST NOT cash-credit Admin Wallet by default; customer recharge/withdraw drive custody cash.

## Requirements

### Requirement: Meal-delivery cash credit path is disabled under custody accounting
When custody accounting is active (customer funding credits Admin Wallet on recharge), the system MUST NOT automatically cash-credit the Admin Wallet for a successful meal-delivery wallet charge. An emergency flag may re-enable legacy `customer_payment` cash credits only when explicitly configured, and operators MUST treat that as a double-count risk.

#### Scenario: Delivered meal does not cash-credit Admin Wallet by default
- **WHEN** an authorized operator marks a delivery `delivered` and the customer wallet is successfully debited `62.00` with meal cash-credit disabled
- **THEN** no new Admin Wallet cash credit increases balance by `62.00` for that delivery payment

#### Scenario: Failed customer charge does not credit Admin Wallet
- **WHEN** mark-delivered fails because the customer wallet has insufficient balance
- **THEN** no Admin Wallet `customer_payment` credit is created for that delivery attempt

### Requirement: Legacy payment source tracking remains available when cash credit is enabled
If the emergency meal cash-credit path is enabled, each automatic Admin Wallet payment credit MUST include source tracking sufficient for admin history: transaction type, amount, credit direction, source/reference labels, related order identifier when available, related delivery identifier when available, customer identifier when available, payment method, note, timestamps, and status. Duplicate credits for the same delivery MUST remain prevented via idempotency.

#### Scenario: History shows order and delivery context when legacy credit exists
- **WHEN** a legacy meal-delivery payment credit exists on the Admin Wallet
- **THEN** the Admin Wallet transaction exposes order and delivery references plus customer context

#### Scenario: Retry does not double credit when legacy path is enabled
- **WHEN** a delivery was already charged and a legacy Admin Wallet credit exists, and mark-delivered is posted again
- **THEN** Admin Wallet balance is unchanged by the retry and only one completed `customer_payment` credit exists for that delivery payment

### Requirement: Customer wallet funding uses custody accounting
Customer wallet recharge and withdraw MUST sync Admin Wallet custody per `admin-wallet-funding-custody` (credit `customer_funding` / debit `customer_withdraw`). The former v1 rule that recharge leaves Admin Wallet unchanged is superseded.

#### Scenario: Customer recharge credits Admin Wallet custody
- **WHEN** a verified customer successfully recharges their personal wallet
- **THEN** the Admin Wallet receives a matching `customer_funding` credit for that recharge
