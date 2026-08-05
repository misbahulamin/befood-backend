## Purpose

Verified-admin configuration and timezone-aware evaluation of customer meal-menu reveal windows.

## Requirements

### Requirement: Admin manages meal reveal windows

The system SHALL store admin-configurable reveal settings for today’s menu visibility: at minimum `lunch_reveal_time`, `dinner_reveal_time`, and a business `timezone`. Defaults MUST be lunch `08:00` and dinner `16:00` in the configured timezone. Only verified admins MAY read and update these settings via admin API.

#### Scenario: Default reveal times

- **WHEN** no custom reveal settings have been saved
- **THEN** the system uses lunch reveal `08:00` and dinner reveal `16:00` in the configured business timezone

#### Scenario: Admin updates reveal times

- **WHEN** a verified admin sets lunch reveal to `07:30` and dinner reveal to `15:30`
- **THEN** subsequent today-menu visibility uses the new times

#### Scenario: Non-admin cannot update reveal settings

- **WHEN** a customer or unauthenticated client attempts to update reveal settings
- **THEN** the system denies the request (`401` or `403`)

### Requirement: Reveal evaluation is timezone-aware

The system MUST evaluate “now” in the configured business timezone when deciding whether lunch and/or dinner for the current local calendar date are visible. Times MUST be compared as local clock times on that date, not ambiguous UTC-only wall clocks without timezone.

#### Scenario: Before lunch reveal

- **WHEN** local time is `07:59` and lunch reveal is `08:00`
- **THEN** today’s lunch menu is not yet visible to customers

#### Scenario: After lunch before dinner

- **WHEN** local time is `12:00`, lunch reveal is `08:00`, and dinner reveal is `16:00`
- **THEN** today’s lunch menu is visible and today’s dinner menu is not yet visible

#### Scenario: After dinner reveal

- **WHEN** local time is `16:05` and dinner reveal is `16:00`
- **THEN** today’s dinner menu is visible (and lunch remains visible for that calendar day)
