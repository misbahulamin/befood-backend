## ADDED Requirements

### Requirement: Admin today-board supports zone, location, and delivery-man filters
The system SHALL extend the admin delivery today-board (or equivalent admin delivery list for a `service_date` + `meal_period`) with optional allowlisted filters `zone_public_id`, `location_public_id`, and `delivery_man_public_id`. Existing date, meal_period, and status filters MUST continue to work. Unsupported filter values MUST be rejected with `400` when validation is enabled.

#### Scenario: Filter today-board by zone
- **WHEN** a verified admin requests the today-board with `zone_public_id` for Zone 1
- **THEN** only deliveries whose customers derive Zone 1 are returned

#### Scenario: Filter by delivery man
- **WHEN** a verified admin requests the today-board with `delivery_man_public_id` for the rider assigned to Zone 2
- **THEN** only deliveries for customers derived in Zone 2 are returned

#### Scenario: Existing filters unchanged
- **WHEN** a verified admin requests the today-board with only `service_date`, `meal_period`, and `status` as today
- **THEN** behavior matches the pre-zone filtering contract (no zone required)
