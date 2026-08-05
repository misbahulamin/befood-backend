## Purpose

Excel-compatible meal cycle costing: additive line costs from `(resolved_kg + flat) × servings`, package rollups with operational other cost and profit, optional estimated kg, and finalized cost snapshots.

## Requirements

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

### Requirement: Optional estimated kilograms from servings

When an ingredient has `customers_per_kg`, the system MAY expose `estimated_kg` as `servings_count / customers_per_kg` on line details for purchasing insight. This MUST NOT replace servings as the primary planning input.

#### Scenario: Estimated kg for rice

- **WHEN** Rice has `customers_per_kg` `7` and servings `60`
- **THEN** line details include `estimated_kg` approximately `8.57`

### Requirement: Snapshot totals on finalize

When a plan is finalized, the system MUST store snapshot values for `product_cost`, `other_cost`, `profit`, `total_cost`, and `per_meal_rate` so later ingredient price edits do not silently change finalized figures until the plan is reopened and recalculated. The stored `total_cost` snapshot MUST also be published as the linked meal’s `total_price`.

#### Scenario: Price change after finalize

- **WHEN** a plan is finalized and an admin later changes Chicken’s `price_per_kg`
- **THEN** the finalized plan’s snapshot totals remain unchanged until reopen + recalculation

#### Scenario: Meal price follows snapshot on finalize

- **WHEN** finalize completes successfully
- **THEN** `MealCategory.total_price` equals the plan’s `snapshot_total_cost`

### Requirement: Snapshot total cost is the published package price

When a plan is finalized, `snapshot_total_cost` MUST be treated as the authoritative package price written to the linked meal’s `total_price`. `snapshot_per_meal_rate` MUST be the authoritative per-meal rate shown for that offering.

#### Scenario: Published price matches snapshot total

- **WHEN** finalize stores `snapshot_total_cost` `4431.93` and `snapshot_per_meal_rate` `73.87`
- **THEN** the meal package price equals `4431.93` and the offering per-meal rate equals `73.87`

### Requirement: Costing fails when ingredient cost is unresolved

The system SHALL NOT treat a missing ingredient cost as zero. When building a plan summary or finalizing a plan, if any line’s ingredient has no resolvable per-serving cost (neither complete kg pricing nor flat `cost_per_customer`), the system MUST return a validation error identifying the ingredient.

#### Scenario: Summary rejected for unpriced line ingredient

- **WHEN** a verified admin requests summary for a plan that includes an ingredient with no resolvable cost
- **THEN** the system returns a validation error and does not return fabricated zero costs for that line

#### Scenario: Finalize rejected for unpriced line ingredient

- **WHEN** a verified admin finalizes a plan that includes an ingredient with no resolvable cost
- **THEN** the system rejects finalize with a validation error and does not lock snapshot totals

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

### Requirement: Package per-meal rate is reference average only for delivery charging

The system SHALL continue to compute and expose package-level `per_meal_rate` from finalized cycle plan totals (`total_cost / expected_servings`) as an estimated average meal rate for offering, eligibility estimates, and admin summaries. The system MUST NOT treat `per_meal_rate` as the authoritative amount to debit from a customer wallet when a delivered meal has a published per-slot final meal price.

#### Scenario: Finalized summary still shows average per_meal_rate

- **WHEN** a verified admin finalizes a cycle plan
- **THEN** the summary includes `per_meal_rate` equal to `total_cost / expected_servings` quantized to money precision

#### Scenario: Average rate is not the delivery charge basis when slot price exists

- **WHEN** a package’s `per_meal_rate` is `50.00` and a published lunch slot for a delivery has final meal price `62.00`
- **THEN** delivery charging uses `62.00` and MUST NOT substitute `50.00` from `per_meal_rate`
