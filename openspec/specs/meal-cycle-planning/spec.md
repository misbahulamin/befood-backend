## Purpose

Month-scoped meal cycle planning: calendar-derived meal counts, per-package servings matrices, summary, finalize, and reopen workflows for verified admins.

## Requirements

### Requirement: Month defines cycle size and meal count

The system SHALL represent a meal cycle by calendar `year` and `month`. For each cycle the system MUST derive `cycle_days` from the calendar month length and MUST set `total_meals` to `cycle_days × 2` as the calendar capacity (full lunch + dinner for every day). Cycle `total_meals` MUST NOT be used as the finalize target for every package plan; each plan’s expected servings MUST come from the linked package’s `meal_type` and `meal_period` for that cycle month.

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

The system SHALL allow a verified admin to create a cycle plan linking one `MealCategory` (meal package) to one `MealCycle`, and to set integer `servings_count` values and a `product_role` per ingredient for that plan. Allowed `product_role` values are `main`, `side`, `staple`, `seasoning`, and `other`. A meal package MUST NOT have duplicate ingredient lines within the same plan. The same ingredient MAY have different `product_role` values on different plans (different packages and/or months).

#### Scenario: Set chicken servings and role for a package

- **WHEN** a verified admin sets `servings_count` to `18` and `product_role` to `main` for Chicken on a draft plan
- **THEN** the system stores the line with that role and includes it in subsequent summaries

#### Scenario: Same ingredient different roles across packages

- **WHEN** Vegetable is `main` on Package A’s plan and `side` on Package D’s plan for the same cycle
- **THEN** the system stores both lines independently and each plan’s finalize/schedule rules use that plan’s role

#### Scenario: Bulk replace plan lines

- **WHEN** a verified admin submits a full servings matrix for a draft plan including `product_role` on each line
- **THEN** the system replaces the plan’s lines atomically with the submitted matrix

#### Scenario: Missing product_role rejected

- **WHEN** a verified admin submits a plan line without `product_role`
- **THEN** the system returns a validation error and does not apply the change

#### Scenario: Duplicate ingredient rejected

- **WHEN** a verified admin tries to add the same ingredient twice to one plan
- **THEN** the system returns a validation error

### Requirement: Plan lines require resolvable ingredient cost

The system SHALL reject adding or replacing a meal-cycle plan line when the referenced ingredient has no resolvable per-serving cost (neither a complete kg pricing pair nor a flat `cost_per_customer`). The error MUST identify the ingredient and MUST NOT treat missing cost as zero.

#### Scenario: Reject unpriced ingredient on plan line

- **WHEN** a verified admin adds a plan line for an ingredient that has neither kg pricing nor `cost_per_customer`
- **THEN** the system returns a validation error and does not create the line

#### Scenario: Accept priced ingredient on plan line

- **WHEN** a verified admin adds a plan line for an ingredient with a complete kg pair or a positive flat `cost_per_customer`
- **THEN** the system stores the line and includes it in subsequent summaries

### Requirement: Admin can view meal details summary before finalize

The system SHALL provide a summary for a cycle plan that lists each line’s servings, cost-per-customer, line product cost, and package-level totals derived from the costing capability. Package-level totals MUST include `expected_servings`, `main_servings_expected` equal to that value, `product_cost`, operational `other_cost` (expected servings × per-meal operational cost for the cycle month), `profit`, `total_cost`, `per_meal_rate`, and the resolved `per_meal_operational_cost`. `expected_servings` MUST be computed from the linked package’s `meal_type`, `meal_period`, and the cycle’s year/month. Summary and costing breakdown fields MUST be available only to verified admins.

#### Scenario: Draft summary uses live prices

- **WHEN** a verified admin requests summary for a draft plan whose cycle month has a resolvable operational cost month
- **THEN** the system recalculates from current ingredient pricing, current monthly per-meal operational cost, and plan `profit_percent`

#### Scenario: Draft summary includes per-meal operational cost

- **WHEN** a verified admin requests summary for a draft plan in a month with `per_meal_operational_cost` `31.00`
- **THEN** the summary includes `per_meal_operational_cost` `31.00` and `other_cost` equal to expected servings times `31.00`

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for plan lines with `product_role=main` equals the plan’s expected servings for the cycle (package meal-period aware), MUST require a resolvable operational cost month for the cycle `(year, month)`, MUST persist snapshot totals (including absolute `other_cost` from operational allocation), MUST set status to `finalized`, MUST publish `snapshot_total_cost` onto the linked meal’s `total_price`, and MUST return the full meal details summary including the published meal price. Summary line details MUST expose each line’s plan-level `product_role`.

#### Scenario: Successful finalize for April

- **WHEN** a draft April plan’s main plan-line servings sum to the expected servings, April has a resolvable operational cost month, and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, per-meal rate, and the meal’s updated `total_price`

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main plan-line servings sum to a value other than expected servings
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals and MUST NOT change the meal’s `total_price`

#### Scenario: Finalize blocked when operational cost missing

- **WHEN** a draft plan’s cycle month has no operational cost month with a valid target meal quantity
- **THEN** the system rejects finalize with a validation error identifying the year and month

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings or product_role
- **THEN** the system rejects the change until the plan is reopened

### Requirement: Reopen keeps last published meal price

When a finalized plan is reopened, the system MUST return the plan to draft for editing and MUST NOT clear the meal’s already published `total_price` until a subsequent finalize overwrites it.

#### Scenario: Reopen does not blank storefront price

- **WHEN** a meal was priced by finalize and the admin reopens that plan
- **THEN** the plan is `draft` and the meal `total_price` remains the previously published value

### Requirement: Menu schedule and sync resolve roles from plan lines

The system SHALL resolve an ingredient’s `product_role` for a monthly menu schedule from the linked `MealCyclePlanLine`, not from the ingredient catalog. Slot assignment validation MUST allow at most one `main` per `(service_date, meal_period)` based on plan-line roles. Publish MUST require exactly one main per required slot using plan-line roles. Admin schedule and sync payloads MUST include `product_role` from the plan line. Customer visibility MUST NOT remove ingredients from admin schedule tooling.

#### Scenario: Vegetable main on one package schedule

- **WHEN** Package A’s plan marks Vegetable as `main` and the admin assigns Vegetable to a lunch slot
- **THEN** that slot treats Vegetable as the main for Package A’s schedule rules

#### Scenario: Same vegetable side on another package

- **WHEN** Package D’s plan marks Vegetable as `side` and the admin assigns Vegetable plus a separate main to a lunch slot
- **THEN** Package D’s schedule accepts Vegetable as a non-main assignment

#### Scenario: Duplicate main rejected using plan roles

- **WHEN** an admin assigns two ingredients that are both `main` on the linked plan to the same slot
- **THEN** the system rejects the assignment

### Requirement: Finalized plan is prerequisite for monthly menu schedule

The system SHALL require a `MealCyclePlan` to be `finalized` before a monthly menu schedule may be created for that plan. Draft plans MUST NOT own a monthly menu schedule.

#### Scenario: Schedule create requires finalized plan

- **WHEN** a verified admin creates a monthly menu schedule for a finalized cycle plan
- **THEN** the system accepts the create

#### Scenario: Schedule create rejected for draft plan

- **WHEN** a verified admin creates a monthly menu schedule for a draft cycle plan
- **THEN** the system rejects the create with a validation error

### Requirement: Admin can reopen a finalized plan

The system SHALL allow a verified admin to reopen a finalized plan, returning it to `draft` so lines and margins can be edited again. If a monthly menu schedule exists for that plan, reopen MUST be rejected while the schedule is `published`; if the schedule is `draft`, reopen MUST either (a) reject until the schedule is deleted, or (b) delete/clear schedule assignments and then reopen. The chosen behavior MUST be consistent and MUST prevent quota-breaking orphan schedules.

#### Scenario: Reopen enables edits

- **WHEN** a verified admin reopens a finalized plan that has no monthly menu schedule
- **THEN** the plan status is `draft` and servings updates are accepted

#### Scenario: Reopen blocked while schedule published

- **WHEN** a verified admin attempts to reopen a finalized plan whose monthly menu schedule is `published`
- **THEN** the system rejects reopen with a conflict or validation error instructing to unpublish or remove the schedule first

#### Scenario: Reopen with draft schedule clears or blocks safely

- **WHEN** a verified admin reopens a finalized plan that has only a `draft` monthly menu schedule
- **THEN** the system either clears that schedule’s assignments (or deletes the schedule) as part of reopen, or rejects reopen until the draft schedule is removed, and MUST NOT leave a schedule that can exceed the reopened plan’s new quotas

### Requirement: Costing details restricted to verified admins

The system MUST expose operational cost ledger data, per-meal operational cost, profit percent on admin costing responses, and meal cost previews only through verified-admin endpoints. Public meal list/detail, customer menu, and order APIs MUST NOT include operational cost items, per-meal operational cost, profit percent, or admin cost-preview breakdowns.

#### Scenario: Public meal detail omits operational costing

- **WHEN** an unauthenticated client retrieves a public meal detail that has a published price
- **THEN** the response does not include operational cost items, `per_meal_operational_cost`, or `profit_percent`

#### Scenario: Verified admin can read costing on plan summary

- **WHEN** a verified admin requests a cycle plan summary
- **THEN** the response includes operational other cost and profit fields used for admin costing
