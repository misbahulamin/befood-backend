## ADDED Requirements

### Requirement: Suggested package price equals total cost

The system SHALL set `suggested_package_price` on plan summaries equal to `total_cost` (quantized to money precision). The system MUST NOT derive `suggested_package_price` from `per_meal_rate × expected_servings` when that would introduce rounding drift from `total_cost`.

#### Scenario: Suggested price matches total for 60-meal package

- **WHEN** a plan summary has `total_cost` `3161.08` and `per_meal_rate` `52.68` for `60` expected servings
- **THEN** `suggested_package_price` is `3161.08` (not `3160.80`)

### Requirement: Published price consistency invariant on finalize

After a successful finalize, the system MUST satisfy `MealCategory.total_price == snapshot_total_cost == summary total_cost` and `published_price_status == in_sync`.

#### Scenario: Finalize publishes exact snapshot total

- **WHEN** finalize computes `total_cost` `3161.08` and persists snapshots
- **THEN** `MealCategory.total_price` is `3161.08` and the finalize response has `published_price_status` `in_sync`

## MODIFIED Requirements

### Requirement: Package cost rollup with overhead and profit

The system SHALL calculate for each cycle plan:

- `product_cost` = sum of line product costs (each line using the additive formula above)
- `per_meal_operational_cost` = resolved value from the operational cost month for the plan’s cycle `(year, month)`
- `other_cost` = `expected_servings × per_meal_operational_cost` (package meal-period aware expected servings)
- `profit` = `product_cost × profit_percent / 100`
- `total_cost` = `product_cost + other_cost + profit`
- `per_meal_rate` = `total_cost /` plan expected servings
- `suggested_package_price` = `total_cost`

The system MUST NOT compute `other_cost` from `other_cost_percent` or any percentage of `product_cost`. `profit_percent` MUST remain configurable per plan. All money values MUST use decimal arithmetic quantized to the project money precision. Profit MUST be calculated on `product_cost` only (operational `other_cost` is excluded from the profit base).

#### Scenario: Per meal rate for 60-meal month

- **WHEN** a plan’s `total_cost` is computed and the cycle has `total_meals` `60` (and expected servings equal `60`)
- **THEN** `per_meal_rate` equals `total_cost / 60` quantized to money precision

#### Scenario: Per meal rate for 62-meal month

- **WHEN** the same product cost structure is applied to a January cycle with `total_meals` `62`
- **THEN** `per_meal_rate` equals `total_cost / 62` (not hardcoded `60`)

#### Scenario: Per meal rate for monthly dinner April package

- **WHEN** a plan’s `total_cost` is computed for a monthly `dinner` package in an April cycle (`expected_servings` `30`)
- **THEN** `per_meal_rate` equals `total_cost / 30` quantized to money precision

#### Scenario: Per meal rate for daily both package

- **WHEN** a plan’s `total_cost` is computed for a daily `both` package (`expected_servings` `2`)
- **THEN** `per_meal_rate` equals `total_cost / 2` quantized to money precision

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

#### Scenario: Profit excludes operational other cost from base

- **WHEN** a plan has `product_cost` `2533.29`, `other_cost` `247.80`, and `profit_percent` `15`
- **THEN** `profit` is `379.99` (`2533.29 × 0.15`), not `15%` of `(product_cost + other_cost)`
