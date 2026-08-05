## ADDED Requirements

### Requirement: Wallet transactions expose meal-payment context for delivery charges

For wallet transactions created as meal-delivery payments (`type=payment` with meal-delivery purpose metadata), the customer wallet transaction list and detail responses MUST expose structured meal-payment fields so clients can render history without relying on undocumented parsing. Exposed fields MUST include at least: meal/package name, service date, meal period (`lunch` or `dinner`), related order public id, and related delivery public id. Non-meal payment transactions MUST omit these fields or return them as null/absent without breaking existing clients.

#### Scenario: List includes meal payment fields after delivered charge

- **WHEN** a verified customer lists wallet transactions after a successful meal-delivery debit
- **THEN** that payment transaction includes meal/package name, service date, meal period, order public id, and delivery public id in the response

#### Scenario: Recharge transaction has no meal payment block

- **WHEN** a verified customer lists wallet transactions that include a `recharge` credit
- **THEN** the recharge item does not present meal-delivery meal period/service date as required meal-payment fields (null/absent)

## MODIFIED Requirements

### Requirement: Customer can list and retrieve owned wallet transactions

The system SHALL provide paginated transaction history for the caller’s wallet, ordered newest first. Each transaction MUST expose `public_id`, `type`, `direction`, `amount`, `balance_after`, `status`, `method`, `note` (nullable/empty allowed), and timestamps. When the transaction is a meal-delivery payment, the response MUST also expose the structured meal-payment context defined by this capability. Transaction detail lookup MUST use `public_id` and MUST enforce ownership. The system MUST NOT expose another customer’s transactions.

#### Scenario: List transactions

- **WHEN** an authenticated verified customer with prior completed transactions requests the transaction list
- **THEN** the system responds `200` with a paginated list of that customer’s transactions ordered newest first

#### Scenario: Transaction detail by public_id

- **WHEN** an authenticated verified customer requests a transaction by its `public_id` that belongs to their wallet
- **THEN** the system responds `200` with that transaction’s public fields

#### Scenario: Foreign transaction is not found

- **WHEN** an authenticated verified customer requests a transaction `public_id` belonging to another customer
- **THEN** the system responds `404 Not Found`

#### Scenario: Meal payment detail includes service context

- **WHEN** an authenticated verified customer retrieves a meal-delivery payment transaction by `public_id`
- **THEN** the response includes meal period, service date, and meal/package name for that payment
