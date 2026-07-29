## MODIFIED Requirements

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

### Requirement: Finalize locks a plan and returns meal details

The system SHALL allow a verified admin to finalize a draft plan. On finalize the system MUST validate that the sum of `servings_count` for plan lines with `product_role=main` equals the plan’s expected servings for the cycle (package meal-period aware), MUST persist snapshot totals, MUST set status to `finalized`, and MUST return the full meal details summary. Summary line details MUST expose each line’s plan-level `product_role`.

#### Scenario: Successful finalize for April

- **WHEN** a draft April plan’s main plan-line servings sum to the expected servings and the admin finalizes
- **THEN** the plan becomes `finalized` and the response includes product cost, other cost, profit, total cost, and per-meal rate

#### Scenario: Finalize blocked when main servings mismatch

- **WHEN** main plan-line servings sum to a value other than expected servings
- **THEN** the system rejects finalize with a validation error identifying the expected and actual totals

#### Scenario: Finalized plan rejects line edits

- **WHEN** a plan is `finalized` and an admin attempts to change servings or product_role
- **THEN** the system rejects the change until the plan is reopened

## ADDED Requirements

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
