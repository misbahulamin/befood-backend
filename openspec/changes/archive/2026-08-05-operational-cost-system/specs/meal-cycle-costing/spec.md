## MODIFIED Requirements

### Requirement: Package cost rollup with overhead and profit

The system SHALL calculate for each cycle plan:

- `product_cost` = sum of line product costs (each line using the additive formula above)
- `per_meal_operational_cost` = resolved value from the operational cost month for the plan’s cycle `(year, month)`
- `other_cost` = `expected_servings × per_meal_operational_cost` (package meal-period aware expected servings)
- `profit` = `product_cost × profit_percent / 100`
- `total_cost` = `product_cost + other_cost + profit`
- `per_meal_rate` = `total_cost /` plan expected servings

The system MUST NOT compute `other_cost` from `other_cost_percent` or any percentage of `product_cost`. `profit_percent` MUST remain configurable per plan. All money values MUST use decimal arithmetic quantized to the project money precision.

#### Scenario: Per meal rate for 60-meal month

- **WHEN** a plan’s `total_cost` is computed and the cycle has `total_meals` `60` (and expected servings equal `60`)
- **THEN** `per_meal_rate` equals `total_cost / 60` quantized to money precision

#### Scenario: Per meal rate for 62-meal month

- **WHEN** the same product cost structure is applied to a January cycle with `total_meals` `62`
- **THEN** `per_meal_rate` equals `total_cost / 62` (not hardcoded `60`)

#### Scenario: Custom profit percent

- **WHEN** a plan sets `profit_percent` to `20`
- **THEN** profit is `product_cost × 0.20` in the summary

#### Scenario: Product cost is sum of additive line costs

- **WHEN** a plan has multiple lines each with computed `line_product_cost` under the additive formula
- **THEN** `product_cost` equals the sum of those `line_product_cost` values

#### Scenario: Other cost from operational allocation

- **WHEN** a plan’s expected servings is `10000` and the cycle month’s `per_meal_operational_cost` is `31.00`
- **THEN** `other_cost` equals `310000.00` and is independent of `product_cost`

#### Scenario: Percent-based other cost is not used

- **WHEN** a plan summary is calculated for a month with a resolvable operational cost
- **THEN** `other_cost` equals `expected_servings × per_meal_operational_cost` even if a legacy `other_cost_percent` value is still present on the plan row

## ADDED Requirements

### Requirement: Costing requires resolvable monthly operational cost

When building a plan summary or finalizing a plan, the system MUST resolve the operational cost month for the plan’s cycle `(year, month)` with `target_meal_quantity > 0`. If resolution fails, the system MUST return a validation error identifying the year and month and MUST NOT fabricate other cost from product-cost percentages.

#### Scenario: Summary rejected when operational month missing

- **WHEN** a verified admin requests summary for a plan whose cycle month has no operational cost month
- **THEN** the system returns a validation error and does not return package totals

#### Scenario: Finalize rejected when operational month missing

- **WHEN** a verified admin finalizes a plan whose cycle month has no operational cost month
- **THEN** the system rejects finalize and does not lock snapshot totals

### Requirement: Admin cost preview for selected ingredients

The system SHALL provide a verified-admin-only cost preview for a cycle plan that returns at least:

- selected ingredients cost (sum of each selected ingredient’s combined unit cost per customer using the additive kg + flat formula)
- `per_meal_operational_cost` for the plan’s cycle month
- `profit_percent` from the plan
- final meal price for one serving computed as:
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
