## Purpose

Authenticated verified customers own one wallet with UUID public identity, balance/status summary, and paginated append-only transaction history.

## Requirements

### Requirement: Customer has exactly one wallet with public identity
The system SHALL ensure each `CustomerProfile` has at most one wallet. The wallet MUST expose opaque `public_id` (UUID) as the client identity and MUST NOT require clients to use the integer primary key. The wallet MUST store `balance` as a non-negative decimal with two fractional digits, `currency` (default `BDT`), and `status` of `active` or `frozen`. Accessing the caller’s wallet when none exists MUST create an active wallet with balance `0`.

#### Scenario: First wallet access creates zero balance
- **WHEN** an authenticated verified customer requests their wallet and no wallet row exists yet
- **THEN** the system creates an active wallet with balance `0.00`, currency `BDT`, and returns it with `public_id`

#### Scenario: Wallet summary for existing wallet
- **WHEN** an authenticated verified customer with an existing wallet requests their wallet
- **THEN** the system responds `200` with `public_id`, `balance`, `currency`, and `status`

#### Scenario: Unauthenticated wallet access rejected
- **WHEN** an unauthenticated client requests the wallet
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Customer cannot read another customer wallet
- **WHEN** an authenticated verified customer calls the wallet endpoint
- **THEN** the system returns only that caller’s wallet and does not accept another customer’s identifier as authorization to view a different wallet

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

### Requirement: Wallet transactions expose meal-payment context for delivery charges

For wallet transactions created as meal-delivery payments (`type=payment` with meal-delivery purpose metadata), the customer wallet transaction list and detail responses MUST expose structured meal-payment fields so clients can render history without relying on undocumented parsing. Exposed fields MUST include at least: meal/package name, service date, meal period (`lunch` or `dinner`), related order public id, and related delivery public id. Non-meal payment transactions MUST omit these fields or return them as null/absent without breaking existing clients.

#### Scenario: List includes meal payment fields after delivered charge

- **WHEN** a verified customer lists wallet transactions after a successful meal-delivery debit
- **THEN** that payment transaction includes meal/package name, service date, meal period, order public id, and delivery public id in the response

#### Scenario: Recharge transaction has no meal payment block

- **WHEN** a verified customer lists wallet transactions that include a `recharge` credit
- **THEN** the recharge item does not present meal-delivery meal period/service date as required meal-payment fields (null/absent)

### Requirement: Meal delivery payment amount matches charged slot price

When a wallet transaction is created for a meal-delivery payment, the transaction `amount` MUST equal the published menu slot final meal price that was debited for that delivery. Wallet history meal-payment context MUST continue to identify `service_date`, `meal_period`, meal/package name, and order/delivery public identifiers so lunch and dinner charges on the same day are distinguishable.

#### Scenario: History amount equals lunch slot charge

- **WHEN** a lunch delivery is charged `62.00` from the published lunch slot final price
- **THEN** the customer’s wallet payment transaction for that delivery has `amount` `62.00` with `meal_period` `lunch` and the corresponding service date

#### Scenario: Dinner charge appears as a separate amount

- **WHEN** a dinner delivery on the same order and date is charged `38.00`
- **THEN** a separate payment debit of `38.00` with `meal_period` `dinner` appears in wallet history

### Requirement: Ledger is the source of truth for balance changes
The system SHALL record every completed balance change as an append-only `WalletTransaction` and MUST update `Wallet.balance` only through the ledger service path. Completed transaction monetary fields MUST NOT be editable via the customer API. Concurrent updates MUST NOT allow the balance to become negative.

#### Scenario: Credit increases balance and writes ledger row
- **WHEN** the ledger service credits a wallet by a positive amount
- **THEN** a credit transaction is stored with `balance_after` equal to the new balance and the wallet balance increases by that amount

#### Scenario: Debit decreases balance and writes ledger row
- **WHEN** the ledger service debits a wallet by a positive amount not exceeding the current balance
- **THEN** a debit transaction is stored with `balance_after` equal to the new balance and the wallet balance decreases by that amount

#### Scenario: Debit rejected when insufficient funds
- **WHEN** the ledger service attempts to debit more than the current balance
- **THEN** the system rejects the operation without changing the balance and without creating a completed debit that would overdraw
