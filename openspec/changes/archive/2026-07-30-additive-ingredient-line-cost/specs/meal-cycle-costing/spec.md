## MODIFIED Requirements

### Requirement: Line product cost from cost per customer and servings

The system SHALL calculate each plan line’s product cost using decimal arithmetic (no binary floating point for money) as:

```text
line_product_cost = (resolved_cost_per_customer + cost_per_customer) × servings_count
```

where:

- `resolved_cost_per_customer` is the kilogram-derived unit cost (`price_per_kg / customers_per_kg`) when the ingredient has a complete kg pair, otherwise treated as `0` in this sum
- `cost_per_customer` is the ingredient’s stored flat per-serving cooking cost when set, otherwise treated as `0` in this sum

The system MUST still reject plan costing when **both** sources are missing (see unresolved-cost requirement). The system MUST NOT use mutually exclusive “kg or flat” selection for line product cost.

#### Scenario: Kg-only line cost

- **WHEN** Beef has kg pricing `650 / 12` (resolved ≈ `54.166667`), no flat `cost_per_customer`, and servings `2`
- **THEN** the line product cost equals `54.166667… × 2` quantized to the project’s money precision rules

#### Scenario: Flat-only line cost

- **WHEN** an ingredient has flat `cost_per_customer` `6.00`, no kg pair, and servings `60`
- **THEN** the line product cost equals `6.00 × 60` quantized to money precision

#### Scenario: Additive kg plus flat line cost

- **WHEN** an ingredient has resolved kg unit `54.166667` and flat `cost_per_customer` `2.00` with servings `10`
- **THEN** the line product cost equals `(54.166667 + 2.00) × 10` quantized to money precision

### Requirement: Package cost rollup with overhead and profit

The system SHALL calculate for each cycle plan:

- `product_cost` = sum of line product costs (each line using the additive formula above)
- `other_cost` = `product_cost × other_cost_percent / 100`
- `profit` = `product_cost × profit_percent / 100`
- `total_cost` = `product_cost + other_cost + profit` (plus operational allocation when applicable per existing meals rules)
- `per_meal_rate` = `total_cost /` plan expected servings (package meal-period aware)

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

#### Scenario: Product cost is sum of additive line costs

- **WHEN** a plan has multiple lines each with computed `line_product_cost` under the additive formula
- **THEN** `product_cost` equals the sum of those `line_product_cost` values
