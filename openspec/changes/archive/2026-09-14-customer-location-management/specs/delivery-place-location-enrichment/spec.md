## ADDED Requirements

### Requirement: Delivery places expose location metadata
The system SHALL include on each delivery place resource the fields `location_source` (`gps` | `manual` | `map_pin` | `search` | `guest_migration` | empty for legacy), optional `location_accuracy` (meters), optional `formatted_address`, and `is_verified_location` (boolean). Existing `latitude` and `longitude` remain the coordinate fields. Clients MUST be able to create a place from GPS/map/search/guest migration with label, full address (or formatted address mapped to full address), latitude, longitude, and source.

#### Scenario: Save GPS location as delivery place
- **WHEN** an authenticated customer creates a delivery place with `location_source=gps`, coordinates, and a full address
- **THEN** the system responds `201` with those fields persisted and `is_verified_location` true when coordinates validate

#### Scenario: Map pin save
- **WHEN** an authenticated customer creates a delivery place with `location_source=map_pin`, latitude, longitude, and full address
- **THEN** the system responds `201` with `location_source=map_pin`

#### Scenario: Manual save with coordinates
- **WHEN** an authenticated customer creates a delivery place with `location_source=manual`, latitude, longitude, and full address
- **THEN** the system responds `201` with the provided metadata

#### Scenario: Search-sourced save
- **WHEN** an authenticated customer creates a delivery place with `location_source=search`, coordinates, and full address
- **THEN** the system responds `201` with `location_source=search`

#### Scenario: Guest migration source
- **WHEN** an authenticated customer creates a place from an accepted guest offer with `location_source=guest_migration`
- **THEN** the system responds `201` with `location_source=guest_migration`

### Requirement: Geo create requires coordinates and address text
The system SHALL reject create/update payloads that set `location_source` to `gps`, `map_pin`, `search`, or `guest_migration` without both latitude and longitude, or without a non-empty address text (`full_address` or `formatted_address`), with `422 Unprocessable Content`.

#### Scenario: GPS without coordinates rejected
- **WHEN** a customer submits `location_source=gps` without latitude or longitude
- **THEN** the system responds `422` and does not create the place

#### Scenario: Coordinates without address text rejected
- **WHEN** a customer submits latitude and longitude for a geo source without address text
- **THEN** the system responds `422` and does not create the place

### Requirement: Nearby duplicate places are rejected excluding self on update
The system SHALL reject creating or geo-updating an active delivery place whose coordinates are within the admin-configured duplicate radius of any **other** active place owned by the same customer that has coordinates. Distance MUST use the shared Haversine helper. When updating an existing place, the system MUST exclude that place’s own id from the comparison. The response MUST use HTTP `422` and `error_code` `LOCATION_ALREADY_EXISTS`.

#### Scenario: Duplicate within radius on create
- **WHEN** a customer already has an active place near 22.357825, 91.846267 and creates another within the configured duplicate radius
- **THEN** the system responds `422` with `error_code=LOCATION_ALREADY_EXISTS` and does not create the place

#### Scenario: Outside radius allowed
- **WHEN** a customer creates a place whose distance to all existing active places with coordinates exceeds the duplicate radius
- **THEN** the system creates the place successfully

#### Scenario: Update same place does not self-match as duplicate
- **WHEN** a customer geo-updates Home to coordinates still within the duplicate radius of its previous position (or identical coords) and no other place conflicts
- **THEN** the system accepts the update and does not return `LOCATION_ALREADY_EXISTS`

#### Scenario: Update colliding with another place rejected
- **WHEN** a customer geo-updates place A to within the duplicate radius of a different active place B
- **THEN** the system responds `422` with `error_code=LOCATION_ALREADY_EXISTS` and does not apply the coordinate change

### Requirement: Address limit uses admin setting and explicit error code
The system SHALL enforce the maximum active delivery places from `CustomerLocationSettings.max_active_delivery_places` (default 3). Creates beyond the limit MUST return `422` with `error_code=ADDRESS_LIMIT_REACHED`. Customers who already have more active places than the current limit MUST retain those places but MUST NOT create additional ones until under the limit.

#### Scenario: Limit reached
- **WHEN** a customer already has the configured maximum active delivery places and attempts to create another
- **THEN** the system responds `422` with `error_code=ADDRESS_LIMIT_REACHED` and does not create the place

#### Scenario: Admin raises limit
- **WHEN** an admin increases `max_active_delivery_places` and a customer under the new limit creates a place
- **THEN** the system creates the place successfully

#### Scenario: Grandfather above new lower limit
- **WHEN** a customer already has more active places than the current max setting
- **THEN** list/retrieve of those places still succeeds and create of an additional place is rejected with `ADDRESS_LIMIT_REACHED`

### Requirement: Location helper is provider-agnostic
The system SHALL expose an internal location helper used by delivery-place services for coordinate validation, distance calculation, and accuracy reliability checks, reusing existing Haversine and accuracy-threshold logic. Reverse geocoding MUST be abstracted so a future provider can be plugged in without changing API contracts; v1 MAY accept client-supplied location names without calling an external geocoder.

#### Scenario: Duplicate check uses shared distance helper
- **WHEN** duplicate detection runs for a new or updated place
- **THEN** distance is computed via the shared location/Haversine helper rather than ad-hoc formulas in the view layer
