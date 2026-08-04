## MODIFIED Requirements

### Requirement: Admin can view meal details summary before finalize

The system SHALL provide a summary for a cycle plan that lists each line’s servings, cost-per-customer, line product cost, and package-level totals derived from the costing capability. Package-level totals MUST include `product_cost`, operational `other_cost` (expected servings × per-meal operational cost for the cycle month), `profit`, `total_cost`, `per_meal_rate`, and the resolved `per_meal_operational_cost`. Summary and costing breakdown fields MUST be available only to verified admins.

#### Scenario: Draft summary uses live prices

- **WHEN** a verified admin requests summary for a draft plan whose cycle month has a resolvable operational cost month
- **THEN** the system recalculates from current ingredient pricing, current monthly per-meal operational cost, and plan `profit_percent`

#### Scenario: Draft summary includes per-meal operational cost

- **WHEN** a verified admin requests summary for a draft plan in a month with `per_meal_operational_cost` `31.00`
- **THEN** the summary includes `per_meal_operational_cost` `31.00` and `other_cost` equal to expected servings times `31.00`

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for plan lines with `product_role=main` equals the plan’s expected servings for the cycle (package meal-period aware), MUST require a resolvable operational cost month for the cycle `(year, month)`, MUST persist snapshot totals (including absolute `other_cost` from operational allocation), MUST set status to `finalized`, and MUST return the full meal details summary. Summary line details MUST expose each line’s plan-level `product_role`.

#### Scenario: Successful finalize for April

- **WHEN** a draft April plan’s main plan-line servings sum to the expected servings, April has a resolvable operational cost month, and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, and per-meal rate

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main plan-line servings sum to a value other than expected servings
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals

#### Scenario: Finalize blocked when operational cost missing

- **WHEN** a draft plan’s cycle month has no operational cost month with a valid target meal quantity
- **THEN** the system rejects finalize with a validation error identifying the year and month

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings or product_role
- **THEN** the system rejects the change until the plan is reopened

## ADDED Requirements

### Requirement: Costing details restricted to verified admins

The system MUST expose operational cost ledger data, per-meal operational cost, profit percent on admin costing responses, and meal cost previews only through verified-admin endpoints. Public meal list/detail, customer menu, and order APIs MUST NOT include operational cost items, per-meal operational cost, profit percent, or admin cost-preview breakdowns.

#### Scenario: Public meal detail omits operational costing

- **WHEN** an unauthenticated client retrieves a public meal detail that has a published price
- **THEN** the response does not include operational cost items, `per_meal_operational_cost`, or `profit_percent`

#### Scenario: Verified admin can read costing on plan summary

- **WHEN** a verified admin requests a cycle plan summary
- **THEN** the response includes operational other cost and profit fields used for admin costing
