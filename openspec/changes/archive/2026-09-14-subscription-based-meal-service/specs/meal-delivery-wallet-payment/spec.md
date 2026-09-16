## MODIFIED Requirements

### Requirement: Wallet debit only when delivery becomes delivered

The system SHALL debit the customer’s wallet for a meal slot if and only if that `OrderDelivery` transitions to status `delivered`. The system MUST NOT debit when the delivery remains `scheduled`, is set to `skipped` (customer meal-off, admin skip, or subscription-cancel skip), or is set to `missed`. **Subscribe** and rolling slot generation MUST NOT debit the wallet for future slots.

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

The system MUST charge the published menu slot’s `final_meal_price` snapshot (two decimal places, BDT) for each successfully delivered slot, matching the subscription’s meal package (or historical order package) and the delivery’s `service_date` and `meal_period`. The system MUST NOT recalculate ingredient cost, operational cost, or profit percent at delivery time for the debit amount. The system MUST NOT debit a package average `per_meal_price_snapshot` or `per_meal_rate` when a slot final price snapshot is available. The system MUST reject the mark-delivered charge path when the matching published slot or its final price snapshot is missing.

#### Scenario: Delivered lunch uses published slot final price

- **WHEN** the package average per-meal rate is `50.00` but the published lunch slot for that delivery’s date has `final_meal_price` `62.00`, and a lunch delivery is marked `delivered` with a sufficient wallet
- **THEN** the wallet is debited by `62.00` and the payment transaction amount is `62.00`

#### Scenario: Delivered dinner charges its own slot price

- **WHEN** the same day’s dinner slot snapshot is `38.00` and that dinner delivery is marked `delivered` with sufficient balance
- **THEN** the wallet is debited `38.00`, not the lunch price and not the package average

#### Scenario: Later catalog price change does not alter delivered charge

- **WHEN** admin later changes ingredient catalog costs after the menu was published, and a still-`scheduled` slot on that subscription is then marked `delivered`
- **THEN** the debit still uses the published slot’s original `final_meal_price` snapshot

#### Scenario: Missing slot price blocks charge

- **WHEN** an operator marks a delivery delivered but no published slot final price exists for that package, date, and meal period
- **THEN** the system rejects the charge, does not complete a meal-payment debit, and does not leave the delivery successfully charged

### Requirement: Meal payment creates a wallet history entry with meal details

On a successful meal-delivery debit, the system MUST create a completed `WalletTransaction` with `type=payment`, `direction=debit`, and status `completed`. The transaction MUST include machine-readable meal context sufficient for wallet history: meal/package name (from subscription snapshot), `service_date`, `meal_period` (`lunch` or `dinner`), charged amount, and stable references to the **subscription** and delivery public identifiers (historical charges MAY still expose order public id). A human-readable `note` MUST summarize the payment (for example meal period and service date).

#### Scenario: Wallet history shows lunch payment details

- **WHEN** a lunch delivery on `2026-08-05` for package name `Premium Meal Package` is charged successfully for `65.00`
- **THEN** the customer’s wallet transaction history includes a payment debit of `65.00` with meal period `lunch`, service date `2026-08-05`, and the package/meal name available to the client

#### Scenario: Dinner payment is distinguishable from lunch

- **WHEN** a dinner delivery on the same subscription and date is marked `delivered` and charged
- **THEN** a separate payment transaction exists with `meal_period=dinner` for that delivery
