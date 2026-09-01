## ADDED Requirements

### Requirement: Spendable balance already reflects pending withdraw reservations
The system SHALL treat `Wallet.balance` as the spendable balance for customer wallet summary, meal-delivery payment debits, and order minimum-balance eligibility. When a pending withdraw has reserved funds by decreasing balance at request create time, those funds MUST NOT remain available for other spending. The customer wallet summary MUST continue to expose the same `balance` field; this change does not require a separate `reserved_balance` response field.

#### Scenario: Wallet summary shows reduced balance after pending withdraw
- **WHEN** a verified customer with balance `500.00` submits a pending withdraw of `200.00` and then requests wallet summary
- **THEN** the wallet `balance` is `300.00`

#### Scenario: Meal payment cannot spend reserved withdraw funds
- **WHEN** a customer’s spendable balance after a pending withdraw reservation is below a meal charge amount
- **THEN** the meal-delivery wallet charge fails for insufficient funds without consuming the reserved pending withdraw amount
