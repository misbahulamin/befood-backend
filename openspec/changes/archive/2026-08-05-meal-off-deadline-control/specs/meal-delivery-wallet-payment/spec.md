## ADDED Requirements

### Requirement: Meal-on does not create a wallet debit

The system MUST NOT create a meal-payment wallet debit when a customer successfully meal-ons a delivery (restores `skipped` → `scheduled`). Charge eligibility MUST resume only if that delivery later transitions to `delivered` under existing delivered-meal payment rules.

#### Scenario: Meal-on leaves wallet balance unchanged

- **WHEN** a verified customer meal-ons a customer-skipped delivery before the deadline
- **THEN** the delivery becomes `scheduled`, no completed meal-payment debit is created for that action, and the wallet balance is unchanged by meal-on

#### Scenario: Later delivered after meal-on charges once

- **WHEN** a customer meal-ons a slot before the deadline and an operator later marks that `scheduled` delivery as `delivered` with a sufficient wallet
- **THEN** exactly one completed meal-payment debit exists for that delivery using the order per-meal price snapshot
