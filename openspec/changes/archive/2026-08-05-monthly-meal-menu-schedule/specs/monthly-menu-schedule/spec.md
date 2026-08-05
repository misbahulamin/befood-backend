## ADDED Requirements

### Requirement: Monthly menu schedule binds to a finalized cycle plan

The system SHALL allow a verified admin to create exactly one monthly menu schedule per `MealCyclePlan`. Creation MUST require that plan’s status to be `finalized`. The schedule MUST cover the cycle’s calendar month using slots of `(service_date, meal_period)` where `meal_period` is `lunch` or `dinner`.

#### Scenario: Create schedule from finalized plan

- **WHEN** a verified admin creates a monthly menu schedule for a finalized cycle plan
- **THEN** the system creates a draft schedule linked to that plan and exposes empty or editable slots for every calendar day in the cycle month for both lunch and dinner

#### Scenario: Reject schedule for draft plan

- **WHEN** a verified admin attempts to create a monthly menu schedule for a draft cycle plan
- **THEN** the system rejects the request with a validation error

#### Scenario: One schedule per plan

- **WHEN** a verified admin attempts to create a second monthly menu schedule for the same cycle plan
- **THEN** the system rejects the request with a conflict or validation error

### Requirement: Slot assignments respect plan servings quotas

The system SHALL allow verified admins to assign ingredients from the linked cycle plan’s lines onto schedule slots. For each ingredient, the count of slot assignments across the schedule MUST NOT exceed that ingredient’s `servings_count` on the linked `MealCyclePlanLine`. Assignments MUST only use ingredients that exist on the linked plan.

#### Scenario: Chicken quota enforced

- **WHEN** a plan allows Chicken `servings_count = 6` and the admin already scheduled Chicken on 6 slots
- **THEN** scheduling Chicken on a seventh slot is rejected with a validation error identifying remaining quota `0`

#### Scenario: Ingredient not on plan rejected

- **WHEN** an admin tries to assign an ingredient that is not a line on the linked cycle plan
- **THEN** the system rejects the assignment

#### Scenario: Bulk save within quotas succeeds

- **WHEN** a verified admin submits a full-month assignment matrix whose per-ingredient totals are within each plan line’s `servings_count`
- **THEN** the system replaces the schedule assignments atomically and returns updated quota usage

### Requirement: Main protein slot fill and period balance rules

The system SHALL treat each `(service_date, meal_period)` slot as requiring at most one ingredient with `product_role=main`. Publishing a schedule MUST require that every slot in the month has exactly one main assignment, and that the total main assignments equals the cycle’s `total_meals`. The system MUST expose remaining quota and lunch/dinner usage counts per ingredient to help admins balance periods (for example preferring a split such as more lunch than dinner when quota is uneven).

#### Scenario: Publish blocked when a slot lacks a main

- **WHEN** any lunch or dinner slot in the month has no `main` ingredient assigned and the admin publishes
- **THEN** the system rejects publish with a validation error listing incomplete slots

#### Scenario: Duplicate main on one slot rejected

- **WHEN** an admin tries to assign two `main` ingredients to the same date and meal period
- **THEN** the system rejects the assignment

#### Scenario: Quota usage shows lunch and dinner split

- **WHEN** an admin requests schedule quota summary after assigning Chicken 8 times to lunch and 4 times to dinner
- **THEN** the response reports Chicken usage `12` with `lunch=8`, `dinner=4`, and remaining based on the plan line

### Requirement: Schedule draft and publish lifecycle for kitchen use

The system SHALL support schedule statuses `draft` and `published`. Only verified admins MAY create, edit, publish, or unpublish schedules. Full-month schedule detail MUST NOT be exposed on public unauthenticated meal APIs. Published schedules are the source of truth for customer today’s-menu data for that package and month.

#### Scenario: Draft edits allowed

- **WHEN** a schedule is `draft` and a verified admin updates slot assignments within quotas
- **THEN** the system accepts the update

#### Scenario: Published schedule still admin-readable for kitchen prep

- **WHEN** a verified admin requests the full monthly schedule for a published schedule
- **THEN** the system returns all dates and meal periods with assigned ingredients for kitchen preparation

#### Scenario: Unauthenticated full-month access denied

- **WHEN** an unauthenticated client requests a full monthly menu schedule
- **THEN** the system returns `401` or otherwise denies access

### Requirement: Side and staple assignments are optional but quota-bound

The system SHALL allow zero or more non-main ingredients (`side`, `staple`, `seasoning`, `other`) on a slot, each still bound by that ingredient’s plan `servings_count`. Publishing MUST NOT require every non-main quota to be fully consumed, unless a future rule is added; remaining non-main quota is allowed.

#### Scenario: Side under-quota publish allowed

- **WHEN** Vegetables has `servings_count = 20` but only 18 slot assignments and all mains are complete
- **THEN** the system allows publish

#### Scenario: Side over-quota rejected

- **WHEN** an admin attempts to assign Vegetables beyond its plan `servings_count`
- **THEN** the system rejects the assignment
