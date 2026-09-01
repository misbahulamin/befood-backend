## ADDED Requirements

### Requirement: Preference and override writes complete when future deliveries need resync

When an authenticated customer successfully updates lunch/dinner defaults or replaces weekday delivery overrides, the system MUST persist the preference change and MUST complete the request successfully even when the customer has future `scheduled` deliveries that require address snapshot resync. The write MUST NOT fail with a server error caused by database row-locking combined with nullable `order` / `subscription` joins on those deliveries. API request and response shapes for preference and override endpoints MUST remain unchanged.

#### Scenario: PUT delivery preferences succeeds with future subscription deliveries

- **WHEN** a verified customer with at least one future `scheduled` subscription-owned delivery puts updated meal delivery preferences
- **THEN** the system responds successfully (not `500`) with the persisted preferences payload

#### Scenario: PUT day overrides succeeds with future scheduled deliveries

- **WHEN** a verified customer with future `scheduled` deliveries replaces their weekday delivery overrides
- **THEN** the system responds successfully (not `500`) with the persisted override list
