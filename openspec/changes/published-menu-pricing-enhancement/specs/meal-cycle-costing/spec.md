## ADDED Requirements

### Requirement: Shared one-meal price calculation

The system SHALL provide a shared decimal money calculation used by subscriber and Instant one-meal pricing with:

```text
profit_amount = ingredient_cost × profit_percent / 100
final_price = ingredient_cost + operational_cost + profit_amount
```

All inputs and outputs MUST use decimal arithmetic quantized to the project money precision. The calculation MUST NOT use binary floating point. Call sites MUST supply the applicable `profit_percent` (cycle plan for subscriber; Instant meal settings for Instant) and MUST NOT hardcode Instant profit.

#### Scenario: Subscriber percent yields known price

- **WHEN** ingredient cost is `100.00`, operational cost is `10.00`, and profit percent is `20`
- **THEN** profit amount is `20.00` and final price is `130.00`

#### Scenario: Instant percent yields known price

- **WHEN** ingredient cost is `100.00`, operational cost is `10.00`, and Instant profit percent is `70`
- **THEN** profit amount is `70.00` and final price is `180.00`

#### Scenario: Cost preview uses shared calculation

- **WHEN** a verified admin requests cycle-plan cost preview for selected ingredients
- **THEN** profit and final meal price equal the shared calculation using plan `profit_percent` and the resolved per-meal operational cost

## MODIFIED Requirements

### Requirement: Admin cost preview for selected ingredients

The system SHALL provide a verified-admin-only cost preview for a cycle plan that returns at least:

- selected ingredients cost (sum of each selected ingredient’s combined unit cost per customer using the additive kg + flat formula)
- `per_meal_operational_cost` for the plan’s cycle month
- `profit_percent` from the plan
- final meal price for one serving computed via the shared one-meal price calculation:
  - `product_cost_one` = selected ingredients unit cost sum
  - `other_cost_one` = `per_meal_operational_cost`
  - `profit_one` = `product_cost_one × profit_percent / 100`
  - `final_meal_price` = `product_cost_one + other_cost_one + profit_one`

Public and customer APIs MUST NOT expose this preview.

#### Scenario: Preview with ingredients and operational cost

- **WHEN** a verified admin requests a cost preview for a plan with selected priced ingredients, July per-meal operational cost `31.00`, and `profit_percent` `10`
- **THEN** the response includes selected ingredients cost, `31.00` per-meal operational cost, profit percent `10`, and the computed final meal price

#### Scenario: Non-admin denied preview

- **WHEN** a customer or unauthenticated client requests the cost preview
- **THEN** the system denies access

#### Scenario: Preview matches shared helper for worked example

- **WHEN** selected ingredients cost is `48.15`, per-meal operational cost is `4.13`, and plan profit percent is `14.45`
- **THEN** profit is `6.96` and final meal price is `59.24` (quantized to project money precision)
