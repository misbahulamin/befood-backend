## MODIFIED Requirements

### Requirement: Confirmation status follows meal-off deadline

For each `(service_date, meal_period)` demand result, the system SHALL set `confirmation_status` to `estimated` while business time (meal-off settings timezone) is at or before that slot’s meal-off deadline, and to `confirmed` after the deadline has passed. Deadline rules MUST reuse existing meal-off settings (lunch: service date at lunch off time; dinner: service date at dinner off time). Admin and kitchen responses MUST expose `confirmation_status` so clients can distinguish provisional vs locked cooking numbers. After confirmation, live recalculation MUST still reflect any admin-driven skips that remain allowed by other flows, but customer meal-off/meal-on MUST already be blocked by existing deadline rules.

#### Scenario: Before dinner deadline status is estimated

- **WHEN** business time on date `D` is before the configured dinner off time and demand for `(D, dinner)` is requested
- **THEN** the response includes `confirmation_status=estimated` and final cooking count equals expected minus current meal-offs

#### Scenario: After dinner deadline status is confirmed

- **WHEN** business time on date `D` is after the configured dinner off time and demand for `(D, dinner)` is requested
- **THEN** the response includes `confirmation_status=confirmed`

#### Scenario: Lunch for D estimated on prior evening

- **WHEN** business time is on `D−1` (evening) and demand for lunch on `D` is requested under default lunch off time `00:00` on `D`
- **THEN** `confirmation_status` is `estimated`

#### Scenario: Lunch for D confirmed after midnight on D

- **WHEN** business time is on `D` after the configured lunch off time and demand for lunch on `D` is requested
- **THEN** `confirmation_status` is `confirmed`
