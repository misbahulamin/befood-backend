# Meal Delivery Wallet Payment

## Purpose
Charge the customer wallet only when a meal delivery is completed, using the published menu slot’s final meal price snapshot and recording an idempotent payment history entry.

## Requirements

### Requirement: Wallet debit only when delivery becomes delivered

The system SHALL debit the customer’s wallet for a meal slot if and only if that `OrderDelivery` transitions to status `delivered`. The system MUST NOT debit when the delivery remains `scheduled`, is set to `skipped` (customer meal-off or admin skip), or is set to `missed`. Order creation and meal schedule generation MUST NOT debit the wallet for future slots.

#### Scenario: Successful delivered meal charges wallet

- **WHEN** an authorized operator marks a `scheduled` delivery as `delivered` and the customer wallet is active with sufficient balance
- **THEN** the delivery status becomes `delivered`, the wallet balance decreases by the charge amount, and exactly one completed payment debit transaction exists for that delivery

#### Scenario: Scheduled delivery is not charged

- **WHEN** a delivery slot exists with status `scheduled`
- **THEN** the system does not create a meal-payment wallet debit for that slot

#### Scenario: Customer meal-off is not charged

- **WHEN** a verified customer successfully meal-offs a `scheduled` delivery (status becomes `skipped`)
- **THEN** the system does not debit the wallet for that slot

#### Scenario: Admin skip is not charged

- **WHEN** an authorized operator marks a delivery as `skipped`
- **THEN** the system does not debit the wallet for that slot

#### Scenario: Missed delivery is not charged

- **WHEN** a delivery is marked `missed` (including lifecycle close-expired behavior)
- **THEN** the system does not debit the wallet for that slot

### Requirement: Charge amount is the published slot final meal price

The system MUST charge the published menu slot’s `final_meal_price` snapshot (two decimal places, BDT) for each successfully delivered slot, matching the order’s meal package and the delivery’s `service_date` and `meal_period`. The system MUST NOT recalculate ingredient cost, operational cost, or profit percent at delivery time for the debit amount. The system MUST NOT debit the order’s average `per_meal_price_snapshot` or package `per_meal_rate` when a slot final price snapshot is available. The system MUST reject the mark-delivered charge path when the matching published slot or its final price snapshot is missing.

#### Scenario: Delivered lunch uses published slot final price

- **WHEN** the package average per-meal rate is `50.00` but the published lunch slot for that delivery’s date has `final_meal_price` `62.00`, and a lunch delivery is marked `delivered` with a sufficient wallet
- **THEN** the wallet is debited by `62.00` and the payment transaction amount is `62.00`

#### Scenario: Delivered dinner charges its own slot price

- **WHEN** the same day’s dinner slot snapshot is `38.00` and that dinner delivery is marked `delivered` with sufficient balance
- **THEN** the wallet is debited `38.00`, not the lunch price and not the package average

#### Scenario: Later catalog price change does not alter delivered charge

- **WHEN** admin later changes ingredient catalog costs after the menu was published, and a still-`scheduled` slot on that order is then marked `delivered`
- **THEN** the debit still uses the published slot’s original `final_meal_price` snapshot

#### Scenario: Missing slot price blocks charge

- **WHEN** an operator marks a delivery delivered but no published slot final price exists for that package, date, and meal period
- **THEN** the system rejects the charge, does not complete a meal-payment debit, and does not leave the delivery successfully charged

### Requirement: Meal payment creates a wallet history entry with meal details

On a successful meal-delivery debit, the system MUST create a completed `WalletTransaction` with `type=payment`, `direction=debit`, and status `completed`. The transaction MUST include machine-readable meal context sufficient for wallet history: meal/package name (from order snapshot), `service_date`, `meal_period` (`lunch` or `dinner`), charged amount, and stable references to the order and delivery public identifiers. A human-readable `note` MUST summarize the payment (for example meal period and service date).

#### Scenario: Wallet history shows lunch payment details

- **WHEN** a lunch delivery on `2026-08-05` for package name `Premium Meal Package` is charged successfully for `65.00`
- **THEN** the customer’s wallet transaction history includes a payment debit of `65.00` with meal period `lunch`, service date `2026-08-05`, and the package/meal name available to the client

#### Scenario: Dinner payment is distinguishable from lunch

- **WHEN** a dinner delivery on the same order and date is marked `delivered` and charged
- **THEN** a separate payment transaction exists with `meal_period=dinner` for that delivery

### Requirement: Duplicate meal payment is prevented

The system MUST ensure at most one successful meal-payment debit exists per `OrderDelivery`. Re-marking the same delivery as `delivered`, concurrent mark requests, or retries MUST NOT create a second completed debit or reduce the wallet balance twice. The system MUST use an idempotency key scoped to the delivery (and/or an equivalent delivery payment-status guard).

#### Scenario: Repeated mark delivered does not double charge

- **WHEN** a delivery is already `delivered` and successfully charged, and an operator posts mark `delivered` again
- **THEN** the delivery remains `delivered`, wallet balance is unchanged by the retry, and only one completed meal-payment debit exists for that delivery

#### Scenario: Concurrent mark delivered charges once

- **WHEN** two concurrent mark-delivered requests target the same `scheduled` delivery with sufficient balance
- **THEN** exactly one completed meal-payment debit is created and the wallet is reduced only once

### Requirement: Insufficient or frozen wallet blocks delivering charge

When marking `delivered` would require a meal-payment debit, the system MUST reject the mark if the wallet is `frozen` or the balance is less than the charge amount. On rejection, the delivery MUST remain `scheduled` (or its prior non-delivered status), and no completed meal-payment debit MUST be created for that attempt.

#### Scenario: Insufficient balance rejects mark delivered

- **WHEN** an operator marks a delivery `delivered` but the customer wallet balance is below the published slot `final_meal_price`
- **THEN** the system rejects the operation with a clear wallet error, the delivery status stays `scheduled`, and the balance is unchanged

#### Scenario: Frozen wallet rejects mark delivered

- **WHEN** an operator marks a delivery `delivered` but the customer wallet status is `frozen`
- **THEN** the system rejects the operation, the delivery status does not become `delivered`, and no completed meal payment is recorded

### Requirement: Payment type is used for meal-delivery wallet charges

The system SHALL record successful meal-delivery wallet charges as ledger transactions with `type=payment` and `direction=debit`, distinct from customer-initiated `withdraw` funding debits and from `recharge` credits. Order create and wallet minimum-balance eligibility checks MUST continue to avoid creating payment debits. Manual recharge and withdraw funding rules from this capability remain unchanged.

#### Scenario: Delivered meal creates payment debit not withdraw

- **WHEN** a delivery is successfully marked `delivered` and the wallet is charged
- **THEN** the ledger row has `type=payment` and `direction=debit`, not `type=withdraw`

#### Scenario: Order create still does not create payment debit

- **WHEN** a verified customer creates a meal package order with sufficient minimum wallet balance
- **THEN** the system does not create a `type=payment` debit solely due to order creation

### Requirement: Meal-on does not create a wallet debit

The system MUST NOT create a meal-payment wallet debit when a customer successfully meal-ons a delivery (restores `skipped` → `scheduled`). Charge eligibility MUST resume only if that delivery later transitions to `delivered` under existing delivered-meal payment rules.

#### Scenario: Meal-on leaves wallet balance unchanged

- **WHEN** a verified customer meal-ons a customer-skipped delivery before the deadline
- **THEN** the delivery becomes `scheduled`, no completed meal-payment debit is created for that action, and the wallet balance is unchanged by meal-on

#### Scenario: Later delivered after meal-on charges once

- **WHEN** a customer meal-ons a slot before the deadline and an operator later marks that `scheduled` delivery as `delivered` with a sufficient wallet
- **THEN** exactly one completed meal-payment debit exists for that delivery using the order per-meal price snapshot
