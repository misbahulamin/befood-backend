## MODIFIED Requirements

### Requirement: Meal-off deadline settings singleton

The system SHALL store a single meal-off settings record with:

- `timezone` (IANA string, default `Asia/Dhaka`)
- `lunch_off_time` (time of day on the **same** calendar day as the lunch service date; default `00:00:00`)
- `dinner_off_time` (time of day on the **same** calendar day as the dinner service date; default `16:00:00`)

Missing settings MUST be created with these defaults on first load.

#### Scenario: Defaults applied on first load

- **WHEN** a verified admin loads meal-off settings and no row exists yet
- **THEN** the response uses timezone `Asia/Dhaka`, lunch off time `00:00:00`, and dinner off time `16:00:00`

### Requirement: Verified admin can update meal-off deadlines

The system SHALL allow a verified admin to view and update meal-off settings. Invalid timezone values MUST be rejected. Updated values MUST apply to subsequent meal-off and meal-on eligibility checks.

#### Scenario: Admin updates dinner off time

- **WHEN** a verified admin patches `dinner_off_time` to `15:00:00`
- **THEN** subsequent dinner meal-off checks use `15:00` on the service date in the settings timezone

#### Scenario: Admin updates lunch off time

- **WHEN** a verified admin patches `lunch_off_time` to `08:00:00`
- **THEN** subsequent lunch meal-off and meal-on checks use `08:00` on the lunch service date in the settings timezone

#### Scenario: Non-admin cannot update settings

- **WHEN** an unauthenticated or non-admin client attempts to update meal-off settings
- **THEN** the system rejects the request with `401` or `403`

#### Scenario: Invalid timezone rejected

- **WHEN** an admin submits a timezone that is not a valid IANA name
- **THEN** the system returns a validation error on `timezone`

### Requirement: Deadline math uses configured times

The system MUST compute lunch and dinner meal-off deadlines from the settings as:

- lunch on `D` → `D + lunch_off_time`
- dinner on `D` → `D + dinner_off_time`

in the configured timezone, and MUST compare against the current time in that timezone (allow while business time is at or before the deadline). The same computed deadline MUST gate both customer meal-off and customer meal-on eligibility for that slot.

#### Scenario: Lunch locks after midnight on the service date

- **WHEN** `lunch_off_time` is `00:00:00` and a customer meal-offs lunch for `2026-07-01` at business time `2026-07-01 00:01`
- **THEN** the system rejects the request because the lunch deadline has passed

#### Scenario: Lunch allowed before midnight on the service date

- **WHEN** `lunch_off_time` is `00:00:00` and a customer meal-offs lunch for `2026-07-01` at business time `2026-06-30 23:59`
- **THEN** the meal-off deadline check allows the request

#### Scenario: Custom lunch off time on service date

- **WHEN** `lunch_off_time` is `08:00:00` and a customer meal-offs lunch for `2026-07-24` at business time `2026-07-24 08:01`
- **THEN** the system rejects the request because the lunch deadline has passed

#### Scenario: Dinner locks after configured afternoon cut-off

- **WHEN** `dinner_off_time` is `16:00:00` and a customer meal-offs dinner for `2026-07-01` at business time `2026-07-01 16:01`
- **THEN** the system rejects the request because the dinner deadline has passed

#### Scenario: Same deadline blocks meal-on after cutoff

- **WHEN** `dinner_off_time` is `16:00:00`, dinner for `2026-08-05` was meal-offed earlier, and business time is `2026-08-05 16:01` in the settings timezone
- **THEN** meal-on for that dinner is rejected because the dinner deadline has passed

#### Scenario: Before configured dinner time meal-on remains allowed

- **WHEN** `dinner_off_time` is `16:00:00`, dinner for `2026-08-05` is customer-skipped, and business time is `2026-08-05 15:59`
- **THEN** meal-on for that dinner is allowed by the deadline check
