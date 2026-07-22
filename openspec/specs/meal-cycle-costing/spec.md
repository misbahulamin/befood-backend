## Purpose

Excel-compatible meal cycle costing: line costs from cost-per-customer × servings, package rollups with overhead and profit, optional estimated kg, and finalized cost snapshots.

## Requirements

### Requirement: Line product cost from cost per customer and servings

The system SHALL calculate each plan line’s product cost as `cost_per_customer × servings_count` using decimal arithmetic (no binary floating point for money).

#### Scenario: Beef line cost

- **WHEN** Beef has `cost_per_customer` `54.166...` (from `650 / 12`) and servings `2`
- **THEN** the line product cost equals `cost_per_customer × 2` quantized to the project’s money precision rules

### Requirement: Package cost rollup with overhead and profit

The system SHALL calculate for each cycle plan:

- `product_cost` = sum of line product costs
- `other_cost` = `product_cost × other_cost_percent / 100`
- `profit` = `product_cost × profit_percent / 100`
- `total_cost` = `product_cost + other_cost + profit`
- `per_meal_rate` = `total_cost / cycle.total_meals`

Default `other_cost_percent` MUST be `30` unless overridden on the plan. `profit_percent` MUST be configurable per plan.

#### Scenario: Per meal rate for 60-meal month

- **WHEN** a plan’s `total_cost` is computed and the cycle has `total_meals` `60`
- **THEN** `per_meal_rate` equals `total_cost / 60` quantized to money precision

#### Scenario: Per meal rate for 62-meal month

- **WHEN** the same product cost structure is applied to a January cycle with `total_meals` `62`
- **THEN** `per_meal_rate` equals `total_cost / 62` (not hardcoded `60`)

#### Scenario: Custom profit percent

- **WHEN** a plan sets `profit_percent` to `20`
- **THEN** profit is `product_cost × 0.20` in the summary

### Requirement: Optional estimated kilograms from servings

When an ingredient has `customers_per_kg`, the system MAY expose `estimated_kg` as `servings_count / customers_per_kg` on line details for purchasing insight. This MUST NOT replace servings as the primary planning input.

#### Scenario: Estimated kg for rice

- **WHEN** Rice has `customers_per_kg` `7` and servings `60`
- **THEN** line details include `estimated_kg` approximately `8.57`

### Requirement: Snapshot totals on finalize

When a plan is finalized, the system MUST store snapshot values for `product_cost`, `other_cost`, `profit`, `total_cost`, and `per_meal_rate` so later ingredient price edits do not silently change finalized figures until the plan is reopened and recalculated.

#### Scenario: Price change after finalize

- **WHEN** a plan is finalized and an admin later changes Chicken’s `price_per_kg`
- **THEN** the finalized plan’s snapshot totals remain unchanged until reopen + recalculation
