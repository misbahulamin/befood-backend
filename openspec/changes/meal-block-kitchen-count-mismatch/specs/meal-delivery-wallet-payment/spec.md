## ADDED Requirements

### Requirement: Successful meal-delivery debit triggers meal-stop evaluation

When a meal-delivery wallet charge succeeds (including via auto-delivery or operator mark-delivered), the system SHALL trigger immediate meal-stop threshold evaluation for that delivery’s customer as specified by `post-meal-charge-meal-stop`. A rejected charge for insufficient funds or frozen wallet MUST NOT mark the delivery delivered and MUST NOT be treated as a successful debit for meal-stop evaluation. Existing debit-on-delivered, amount, idempotency, and Admin Wallet non-cash-credit rules from this capability remain unchanged.

#### Scenario: Successful delivered charge evaluates meal-stop

- **WHEN** a `scheduled` delivery becomes `delivered` and the wallet is successfully debited for the slot price
- **THEN** the system evaluates the customer’s post-debit spendable balance against `meal_stop_threshold` and applies meal-stop block when balance is strictly below the threshold

#### Scenario: Insufficient funds rejection does not meal-stop via charge path

- **WHEN** mark-delivered is rejected because wallet balance is below the meal charge amount
- **THEN** the delivery is not charged, and this rejection alone does not constitute a successful meal-payment debit for post-charge meal-stop evaluation
