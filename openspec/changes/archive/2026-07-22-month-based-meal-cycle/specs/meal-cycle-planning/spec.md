## ADDED Requirements

### Requirement: Month defines cycle size and meal count

The system SHALL represent a meal cycle by calendar `year` and `month`. For each cycle the system MUST derive `cycle_days` from the calendar month length and MUST set `total_meals` to `cycle_days × 2` (two meals per day).

#### Scenario: January cycle

- **WHEN** a verified admin creates a cycle for year `2026` month `1`
- **THEN** `cycle_days` is `31` and `total_meals` is `62`

#### Scenario: April cycle

- **WHEN** a verified admin creates a cycle for year `2026` month `4`
- **THEN** `cycle_days` is `30` and `total_meals` is `60`

#### Scenario: Unique year-month

- **WHEN** a verified admin attempts to create a second cycle for the same year and month
- **THEN** the system rejects the request with a conflict or validation error

### Requirement: Admin plans servings per meal package in a cycle

The system SHALL allow a verified admin to create a cycle plan linking one `MealCategory` (meal package) to one `MealCycle`, and to set integer `servings_count` values per ingredient for that plan. A meal package MUST NOT have duplicate ingredient lines within the same plan.

#### Scenario: Set chicken servings for a package

- **WHEN** a verified admin sets `servings_count` to `18` for Chicken on a draft plan
- **THEN** the system stores the line and includes it in subsequent summaries

#### Scenario: Bulk replace plan lines

- **WHEN** a verified admin submits a full servings matrix for a draft plan
- **THEN** the system replaces the plan’s lines atomically with the submitted matrix

#### Scenario: Duplicate ingredient rejected

- **WHEN** a verified admin tries to add the same ingredient twice to one plan
- **THEN** the system returns a validation error

### Requirement: Admin can view meal details summary before finalize

The system SHALL provide a summary for a cycle plan that lists each line’s servings, cost-per-customer, line product cost, and package-level totals derived from the costing capability.

#### Scenario: Draft summary uses live prices

- **WHEN** a verified admin requests summary for a draft plan
- **THEN** the system recalculates from current ingredient pricing and plan margins

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for ingredients with `product_role=main` equals the cycle’s `total_meals`, MUST persist snapshot totals, MUST set status to `finalized`, and MUST return the full meal details summary.

#### Scenario: Successful finalize for April

- **WHEN** a draft April plan’s main servings sum to `60` and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, and per-meal rate

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main servings sum to a value other than `total_meals`
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings
- **THEN** the system rejects the change until the plan is reopened

### Requirement: Admin can reopen a finalized plan

The system SHALL allow a verified admin to reopen a finalized plan, returning it to `draft` so lines and margins can be edited again.

#### Scenario: Reopen enables edits

- **WHEN** a verified admin reopens a finalized plan
- **THEN** the plan status is `draft` and servings updates are accepted

### Requirement: Public meal APIs remain unchanged

The system MUST NOT expose cycle planning or ingredient costing data on public customer meal list/detail endpoints as part of this capability.

#### Scenario: Public meal list unchanged

- **WHEN** an unauthenticated client lists meals
- **THEN** the response does not include cycle plans, servings matrices, or costing breakdowns
