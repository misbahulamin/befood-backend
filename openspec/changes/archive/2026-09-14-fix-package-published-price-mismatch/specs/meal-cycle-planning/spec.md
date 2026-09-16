## ADDED Requirements

### Requirement: Summary exposes published price sync status

The system SHALL include `published_price_status` and `published_price_delta` on every cycle plan summary response.

- `published_price_status` MUST be `in_sync` when `published_meal_total_price` equals `total_cost` (or both are absent/null-equivalent).
- `published_price_status` MUST be `stale` when `published_meal_total_price` is present and differs from the summary’s `total_cost`.
- `published_price_delta` MUST be the decimal-string difference `total_cost − published_meal_total_price` when status is `stale`, and MUST be `null` when `in_sync`.

`published_meal_total_price` MUST continue to reflect `MealCategory.total_price` (last published value). `total_cost` MUST continue to reflect live calculation on draft plans and snapshot values on finalized plans.

#### Scenario: Finalized plan summary is in sync

- **WHEN** a verified admin requests summary for a finalized plan whose `snapshot_total_cost` was published to `MealCategory.total_price`
- **THEN** `published_price_status` is `in_sync`, `published_price_delta` is `null`, and `published_meal_total_price` equals `total_cost`

#### Scenario: Draft summary stale after operational cost increase

- **WHEN** a plan was finalized and published at `total_cost` `3113.66`, the plan is reopened (or a new draft plan exists for the package), the operational cost ledger for the cycle month increases so live `other_cost` rises by `47.42`, and the admin requests summary
- **THEN** live `total_cost` is `3161.08`, `published_meal_total_price` remains `3113.66`, `published_price_status` is `stale`, and `published_price_delta` is `47.42`

#### Scenario: Draft summary stale when no prior publish

- **WHEN** a draft plan has a computed `total_cost` but `MealCategory.total_price` is `null`
- **THEN** `published_price_status` is `in_sync` and `published_meal_total_price` is `null`

## MODIFIED Requirements

### Requirement: Admin can view meal details summary before finalize

The system SHALL provide a summary for a cycle plan that lists each line’s servings, cost-per-customer, line product cost, and package-level totals derived from the costing capability. Package-level totals MUST include `expected_servings`, `main_servings_expected` equal to that value, `product_cost`, operational `other_cost` (expected servings × per-meal operational cost for the cycle month), `profit`, `total_cost`, `per_meal_rate`, the resolved `per_meal_operational_cost`, `published_meal_total_price` (from `MealCategory.total_price`), `published_price_status`, and `published_price_delta`. `expected_servings` MUST be computed from the linked package’s `meal_type`, `meal_period`, and the cycle’s year/month. Summary and costing breakdown fields MUST be available only to verified admins.

#### Scenario: Draft summary uses live prices

- **WHEN** a verified admin requests summary for a draft plan whose cycle month has a resolvable operational cost month
- **THEN** the system recalculates from current ingredient pricing, current monthly per-meal operational cost, and plan `profit_percent`

#### Scenario: Draft summary includes per-meal operational cost

- **WHEN** a verified admin requests summary for a draft plan in a month with `per_meal_operational_cost` `31.00`
- **THEN** the summary includes `per_meal_operational_cost` `31.00` and `other_cost` equal to expected servings times `31.00`

#### Scenario: Summary for monthly lunch in January

- **WHEN** a verified admin requests summary for a January plan linked to a monthly `lunch` package
- **THEN** `expected_servings` and `main_servings_expected` are `31`

#### Scenario: Draft summary shows stale published price with live total

- **WHEN** a verified admin requests summary for a draft plan and `MealCategory.total_price` differs from the live `total_cost`
- **THEN** the response includes both values, `published_price_status` `stale`, and a non-null `published_price_delta`
