## ADDED Requirements

### Requirement: Meal delivery payment amount matches charged slot price

When a wallet transaction is created for a meal-delivery payment, the transaction `amount` MUST equal the published menu slot final meal price that was debited for that delivery. Wallet history meal-payment context MUST continue to identify `service_date`, `meal_period`, meal/package name, and order/delivery public identifiers so lunch and dinner charges on the same day are distinguishable.

#### Scenario: History amount equals lunch slot charge

- **WHEN** a lunch delivery is charged `62.00` from the published lunch slot final price
- **THEN** the customer’s wallet payment transaction for that delivery has `amount` `62.00` with `meal_period` `lunch` and the corresponding service date

#### Scenario: Dinner charge appears as a separate amount

- **WHEN** a dinner delivery on the same order and date is charged `38.00`
- **THEN** a separate payment debit of `38.00` with `meal_period` `dinner` appears in wallet history
