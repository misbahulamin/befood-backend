## ADDED Requirements

### Requirement: Meal price charging independent of delivery fee preference

Per-meal wallet debit on delivery mark remains governed by existing meal payment rules and slot prices. Subscription meal preference MUST only control which period slots exist; it MUST NOT change the per-meal charge amount formula. Monthly delivery fee calculation and debit remain a separate wallet concern from meal payment.

#### Scenario: Lunch-only delivered meal charges meal price only

- **WHEN** a lunch-only subscriber’s lunch slot is marked delivered
- **THEN** the wallet is debited the canonical meal amount for that slot and no delivery-fee payment is created by the meal payment path

#### Scenario: Preference does not alter meal payment metadata shape

- **WHEN** a meal payment succeeds for a dinner-only subscription delivery
- **THEN** the transaction still uses existing meal payment type/metadata (including `meal_period`) without requiring delivery-fee fields
