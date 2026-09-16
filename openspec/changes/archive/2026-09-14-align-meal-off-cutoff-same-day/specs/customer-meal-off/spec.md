## MODIFIED Requirements

### Requirement: Meal-off enforces period deadlines

The system MUST reject meal-off when the current business time is after the deadline for that slot:

- For `meal_period=lunch` on service date `D`, the deadline is calendar date `D` at the configured lunch off time (default `00:00`).
- For `meal_period=dinner` on service date `D`, the deadline is calendar date `D` at the configured dinner off time (default `16:00`).

Deadline evaluation MUST use the meal-off settings timezone. Business time at or before the deadline MUST remain allowed.

#### Scenario: Lunch for the 1st blocked after midnight on the 1st

- **WHEN** business time is `2026-07-01 00:01` (settings timezone) and the customer meal-offs lunch for `2026-07-01`
- **THEN** the system rejects the request because the lunch deadline (`2026-07-01 00:00`) has passed

#### Scenario: Lunch for the 1st allowed before midnight on the 1st

- **WHEN** business time is `2026-06-30 23:50` and the customer meal-offs lunch for `2026-07-01`
- **THEN** the meal-off succeeds

#### Scenario: Dinner for the 1st blocked after 16:00

- **WHEN** business time is `2026-07-01 16:01` and the customer meal-offs dinner for `2026-07-01` with default dinner off time `16:00`
- **THEN** the system rejects the request

#### Scenario: Dinner for the 1st allowed before 16:00

- **WHEN** business time is `2026-07-01 15:59` and the customer meal-offs dinner for `2026-07-01` with default dinner off time `16:00`
- **THEN** the meal-off succeeds

### Requirement: Deadline locks both meal-off and meal-on

The system MUST reject meal-off and meal-on when business time is after the deadline for that slot. When rejected for deadline, the system MUST leave the delivery status and skip markers unchanged. Deadline evaluation MUST use the same rules and timezone as meal-off settings:

- For `meal_period=lunch` on service date `D`, the deadline is calendar date `D` at the configured lunch off time.
- For `meal_period=dinner` on service date `D`, the deadline is calendar date `D` at the configured dinner off time.

#### Scenario: After dinner deadline neither off nor on is allowed

- **WHEN** business time on service date `D` is after the configured dinner off time and the dinner delivery for `D` is still `scheduled`
- **THEN** meal-off is rejected and the delivery remains `scheduled`

#### Scenario: After dinner deadline meal-on of prior off is rejected

- **WHEN** dinner for `D` was meal-offed earlier and business time on `D` is after the dinner off time
- **THEN** meal-on is rejected and the delivery remains `skipped`

#### Scenario: Before dinner deadline customer may toggle off then on

- **WHEN** business time on service date `D` is before the dinner off time
- **THEN** the customer may meal-off then meal-on the dinner slot successfully

#### Scenario: After lunch midnight cut-off meal-on is rejected

- **WHEN** lunch for `D` was meal-offed earlier and business time on `D` is after `lunch_off_time` (default `00:00`)
- **THEN** meal-on is rejected and the delivery remains `skipped`
