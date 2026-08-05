## MODIFIED Requirements

### Requirement: Package cost rollup with overhead and profit

The system SHALL calculate for each cycle plan:

- `product_cost` = sum of line product costs
- `other_cost` = `product_cost × other_cost_percent / 100`
- `profit` = `product_cost × profit_percent / 100`
- `total_cost` = `product_cost + other_cost + profit`
- `per_meal_rate` = `total_cost / expected_servings`

where `expected_servings` is derived from the linked package’s `meal_type` and `meal_period` for the plan’s cycle year/month (not unconditionally `cycle.total_meals`).

Default `other_cost_percent` MUST be `30` unless overridden on the plan. `profit_percent` MUST be configurable per plan. Division MUST reject or guard against non-positive expected servings.

#### Scenario: Per meal rate for monthly both April package

- **WHEN** a plan’s `total_cost` is computed for a monthly `both` package in an April cycle (`expected_servings` `60`)
- **THEN** `per_meal_rate` equals `total_cost / 60` quantized to money precision

#### Scenario: Per meal rate for monthly dinner April package

- **WHEN** a plan’s `total_cost` is computed for a monthly `dinner` package in an April cycle (`expected_servings` `30`)
- **THEN** `per_meal_rate` equals `total_cost / 30` quantized to money precision

#### Scenario: Per meal rate for daily both package

- **WHEN** a plan’s `total_cost` is computed for a daily `both` package (`expected_servings` `2`)
- **THEN** `per_meal_rate` equals `total_cost / 2` quantized to money precision

#### Scenario: Custom profit percent

- **WHEN** a plan sets `profit_percent` to `20`
- **THEN** profit is `product_cost × 0.20` in the summary
