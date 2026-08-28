## Purpose

Verified-admin configuration for Instant Meal profit margin and public display duration window.

## ADDED Requirements

### Requirement: Admin manages Instant Meal profit and duration

The system SHALL store Instant Meal settings as a singleton configuration with at least `profit_percent` and `duration_days`. Default `profit_percent` MUST be `50.00`. Allowed `duration_days` values MUST be exactly the set `{1, 3, 7, 15, 25, 30}` where `1` means Today only. Only verified admins MAY read and update these settings via admin API. The system MUST reject updates that set `duration_days` outside the allowlist.

#### Scenario: Default Instant profit is fifty percent

- **WHEN** Instant Meal settings have never been customized
- **THEN** the system uses `profit_percent` = `50.00`

#### Scenario: Admin updates Instant profit percent

- **WHEN** a verified admin sets Instant `profit_percent` to `70`
- **THEN** subsequent Instant Meal price calculations use `70` percent profit on ingredient cost

#### Scenario: Admin selects seven-day display window

- **WHEN** a verified admin sets `duration_days` to `7`
- **THEN** the Instant Meal list window spans seven inclusive local calendar days starting today

#### Scenario: Invalid duration rejected

- **WHEN** a verified admin attempts to set `duration_days` to `10`
- **THEN** the system rejects the update with a validation error and leaves prior settings unchanged

#### Scenario: Non-admin cannot update Instant Meal settings

- **WHEN** a customer or unauthenticated client attempts to update Instant Meal settings
- **THEN** the system denies the request (`401` or `403`)

### Requirement: Instant settings are isolated from subscription plan profit

Instant Meal `profit_percent` MUST be stored and applied independently from each `MealCyclePlan.profit_percent`. Updating Instant settings MUST NOT rewrite cycle plan profit fields or published subscription slot price snapshots.

#### Scenario: Instant profit change does not alter cycle plan profit

- **WHEN** a cycle plan has `profit_percent` = `10` and an admin sets Instant `profit_percent` to `70`
- **THEN** that cycle plan’s `profit_percent` remains `10`
