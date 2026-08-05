## ADDED Requirements

### Requirement: Snapshot total cost is the published package price

When a plan is finalized, `snapshot_total_cost` MUST be treated as the authoritative package price written to the linked meal’s `total_price`. `snapshot_per_meal_rate` MUST be the authoritative per-meal rate shown for that offering.

#### Scenario: Published price matches snapshot total

- **WHEN** finalize stores `snapshot_total_cost` `4431.93` and `snapshot_per_meal_rate` `73.87`
- **THEN** the meal package price equals `4431.93` and the offering per-meal rate equals `73.87`

## MODIFIED Requirements

### Requirement: Snapshot totals on finalize

When a plan is finalized, the system MUST store snapshot values for `product_cost`, `other_cost`, `profit`, `total_cost`, and `per_meal_rate` so later ingredient price edits do not silently change finalized figures until the plan is reopened and recalculated. The stored `total_cost` snapshot MUST also be published as the linked meal’s `total_price`.

#### Scenario: Price change after finalize

- **WHEN** a plan is finalized and an admin later changes Chicken’s `price_per_kg`
- **THEN** the finalized plan’s snapshot totals remain unchanged until reopen + recalculation

#### Scenario: Meal price follows snapshot on finalize

- **WHEN** finalize completes successfully
- **THEN** `MealCategory.total_price` equals the plan’s `snapshot_total_cost`
