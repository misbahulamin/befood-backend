## ADDED Requirements

### Requirement: Cross-package sync suggestions within a cycle

The system SHALL provide a verified-admin sync suggestion for a target monthly menu schedule based on one or more source schedules (or a primary package schedule) in the same `MealCycle`. Suggestions MUST prefer matching the same ingredient on the same `(service_date, meal_period)` across packages to optimize shared cooking, while NEVER proposing an assignment that would exceed the target plan’s `servings_count` for that ingredient.

#### Scenario: Mirror chicken where quota allows

- **WHEN** Regular Package has Chicken on 2026-07-22 lunch and Student Package still has remaining Chicken quota
- **THEN** the sync suggestion for Student Package includes Chicken on 2026-07-22 lunch

#### Scenario: Skip when target quota exhausted

- **WHEN** Regular Package has Chicken on a slot but Student Package Chicken remaining quota is `0`
- **THEN** the suggestion omits Chicken for that slot on Student Package and may propose the next-best available main from the student plan (or leave the slot for manual fill)

#### Scenario: Different package quotas do not force over-assign

- **WHEN** Regular Package Chicken quota is `12` and Student Package Chicken quota is `10`
- **THEN** sync suggestions for Student Package propose at most `10` Chicken slots even if Regular scheduled `12`

### Requirement: Apply sync is explicit and transactional

The system SHALL allow a verified admin to apply a sync suggestion to a draft (or explicitly editable) target schedule in one transaction. Apply MUST validate all quota and main-slot rules before committing. The system MUST NOT silently overwrite published customer-visible schedules without an admin action that either works on draft or follows an unpublish/edit/publish flow defined by the schedule lifecycle.

#### Scenario: Apply suggestion succeeds within quotas

- **WHEN** a verified admin applies a valid sync suggestion to a draft target schedule
- **THEN** the target schedule assignments update to the suggested set and quota usage reflects the new counts

#### Scenario: Apply rejected on conflict

- **WHEN** applying a suggestion would place two mains on one slot or exceed a quota
- **THEN** the system rejects the apply with a validation error and leaves the prior assignments unchanged

### Requirement: Lunch and dinner balance guidance

The system SHALL include lunch/dinner balance metrics in sync and quota views: per ingredient, count of lunch vs dinner assignments, and a recommended balanced split for remaining quota (preferring as even a split as possible, with any remainder preferring lunch when counts are odd, unless the admin supplies an explicit preference). Auto-suggestion of unplaced remaining mains MUST use that balance heuristic when placing into empty slots.

#### Scenario: Odd remaining prefers lunch

- **WHEN** an ingredient has `3` unplaced servings left and empty slots exist in both periods
- **THEN** the suggestion places `2` on lunch and `1` on dinner (or documents the configured preference equivalently)

#### Scenario: Divergence warning across packages

- **WHEN** two published or draft schedules in the same cycle assign different main ingredients on the same date and meal period
- **THEN** the sync or schedule comparison response includes a divergence warning for that slot
