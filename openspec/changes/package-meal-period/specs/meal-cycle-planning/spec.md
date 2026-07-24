## MODIFIED Requirements

### Requirement: Month defines cycle size and meal count

The system SHALL represent a meal cycle by calendar `year` and `month`. For each cycle the system MUST derive `cycle_days` from the calendar month length and MUST set `total_meals` to `cycle_days × 2` as the **calendar capacity** (full lunch + dinner for every day). Cycle `total_meals` MUST NOT be used as the finalize target for every package plan; each plan’s expected servings MUST come from the linked package’s `meal_type` and `meal_period` for that cycle month.

#### Scenario: January cycle

- **WHEN** a verified admin creates a cycle for year `2026` month `1`
- **THEN** `cycle_days` is `31` and `total_meals` is `62`

#### Scenario: April cycle

- **WHEN** a verified admin creates a cycle for year `2026` month `4`
- **THEN** `cycle_days` is `30` and `total_meals` is `60`

#### Scenario: Unique year-month

- **WHEN** a verified admin attempts to create a second cycle for the same year and month
- **THEN** the system rejects the request with a conflict or validation error

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for ingredients with `product_role=main` equals the plan’s **expected servings** for the linked package (`expected_servings(meal_type, meal_period, cycle.year, cycle.month)`), MUST persist snapshot totals, MUST set status to `finalized`, and MUST return the full meal details summary including `expected_servings`.

#### Scenario: Successful finalize for April monthly both

- **WHEN** a draft April plan for a monthly `both` package has main servings summing to `60` and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, per-meal rate, and `expected_servings` `60`

#### Scenario: Successful finalize for April monthly dinner

- **WHEN** a draft April plan for a monthly `dinner` package has main servings summing to `30` and the admin finalizes
- **THEN** the plan becomes `finalized` and `expected_servings` is `30`

#### Scenario: Successful finalize for daily both

- **WHEN** a draft plan for a daily `both` package has main servings summing to `2` and the admin finalizes
- **THEN** the plan becomes `finalized` and `expected_servings` is `2`

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main servings sum to a value other than the package’s expected servings for the cycle month
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings
- **THEN** the system rejects the change until the plan is reopened

## ADDED Requirements

### Requirement: Plan summary exposes package expected servings

The system SHALL include `expected_servings` (and `main_servings_expected` equal to that value) on cycle plan summary responses, computed from the linked package’s `meal_type`, `meal_period`, and the cycle’s year/month.

#### Scenario: Summary for monthly lunch in January

- **WHEN** a verified admin requests summary for a January plan linked to a monthly `lunch` package
- **THEN** `expected_servings` and `main_servings_expected` are `31`
