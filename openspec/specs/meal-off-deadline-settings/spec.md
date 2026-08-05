# Meal-Off Deadline Settings

## Purpose
Define admin-configurable cutoffs that determine until when a customer may meal-off lunch and dinner deliveries.

## Requirements

### Requirement: Meal-off deadline settings singleton

The system SHALL store a single meal-off settings record with:

- `timezone` (IANA string, default `Asia/Dhaka`)
- `lunch_off_time` (time of day on the **previous** calendar day relative to the lunch service date; default `23:59:00`)
- `dinner_off_time` (time of day on the **same** calendar day as the dinner service date; default `14:00:00`)

Missing settings MUST be created with these defaults on first load.

#### Scenario: Defaults applied on first load

- **WHEN** a verified admin loads meal-off settings and no row exists yet
- **THEN** the response uses timezone `Asia/Dhaka`, lunch off time `23:59:00`, and dinner off time `14:00:00`

### Requirement: Verified admin can update meal-off deadlines

The system SHALL allow a verified admin to view and update meal-off settings. Invalid timezone values MUST be rejected. Updated values MUST apply to subsequent meal-off eligibility checks.

#### Scenario: Admin updates dinner off time

- **WHEN** a verified admin patches `dinner_off_time` to `15:00:00`
- **THEN** subsequent dinner meal-off checks use `15:00` on the service date in the settings timezone

#### Scenario: Non-admin cannot update settings

- **WHEN** an unauthenticated or non-admin client attempts to update meal-off settings
- **THEN** the system rejects the request with `401` or `403`

#### Scenario: Invalid timezone rejected

- **WHEN** an admin submits a timezone that is not a valid IANA name
- **THEN** the system returns a validation error on `timezone`

### Requirement: Deadline math uses configured times

The system MUST compute lunch and dinner meal-off deadlines from the settings as:

- lunch on `D` → `(D − 1) + lunch_off_time`
- dinner on `D` → `D + dinner_off_time`

in the configured timezone, and MUST compare against the current time in that timezone.

#### Scenario: Custom lunch off time moves deadline

- **WHEN** `lunch_off_time` is `22:00:00` and a customer meal-offs lunch for `2026-07-24` at business time `2026-07-23 22:30`
- **THEN** the system rejects the request because the lunch deadline has passed
