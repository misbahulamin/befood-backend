## ADDED Requirements

### Requirement: Instant display pricing must not mutate subscriber slot snapshots

The system SHALL allow Instant meal selling prices to be derived with Instant meal settings `profit_percent` using the shared one-meal formula and the slot’s cost basis. Computing or returning Instant prices for admin published-menu detail or Instant meal cards MUST NOT update `final_meal_price_snapshot`, `ingredient_cost_snapshot`, `operational_cost_snapshot`, `profit_snapshot`, or cycle plan `profit_percent`.

#### Scenario: Instant percent patch leaves subscriber snapshot intact

- **WHEN** a published lunch slot has `final_meal_price_snapshot` `59.24` and an admin updates Instant `profit_percent`
- **THEN** the lunch slot’s `final_meal_price_snapshot` remains `59.24` and Instant display price may change on the next read

#### Scenario: Delivery charge still uses subscriber snapshot

- **WHEN** Instant display price for a slot differs from `final_meal_price_snapshot` because Instant profit percent is higher
- **THEN** subscription delivery wallet debit continues to use `final_meal_price_snapshot`, not the Instant display price
