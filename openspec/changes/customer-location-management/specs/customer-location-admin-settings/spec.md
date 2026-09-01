## ADDED Requirements

### Requirement: Singleton customer location settings
The system SHALL provide a singleton `CustomerLocationSettings` (pk=1) with `duplicate_radius_km` (default 0.5), `max_active_delivery_places` (default 3), and `location_refresh_interval_hours` (default 24). Settings MUST be readable and updatable by verified admins via Django admin and a documented web API. Delivery-place and location-preference services MUST read live values from this singleton (via `.load()`), not hardcoded constants. GPS accuracy soft-warning threshold MUST continue to use existing `SERVICE_AREA_ACCURACY_THRESHOLD_M` (default 500) unless later promoted into this singleton.

#### Scenario: Defaults on first load
- **WHEN** settings are loaded and no row exists yet
- **THEN** the system creates defaults duplicate_radius_km=0.5, max_active_delivery_places=3, location_refresh_interval_hours=24

#### Scenario: Admin updates duplicate radius
- **WHEN** a verified admin sets `duplicate_radius_km` to a new positive value
- **THEN** subsequent duplicate detection uses the new radius

#### Scenario: Admin updates max addresses
- **WHEN** a verified admin sets `max_active_delivery_places` to 5
- **THEN** customers with fewer than 5 active places may create until that cap

#### Scenario: Non-admin cannot update settings
- **WHEN** a non-admin client attempts to update location settings
- **THEN** the system responds `401` or `403` per existing admin API auth rules
