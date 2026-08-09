## ADDED Requirements

### Requirement: Customer can check serviceability by coordinates
The system SHALL expose `POST /api/v1/service-areas/check` that accepts `latitude` and `longitude` (required), optional `accuracy` in meters, and optional nullable `location_name`. The endpoint MUST be usable by guests and authenticated customers. The system MUST NOT derive customer location from IP address for this check.

#### Scenario: Successful check with location name
- **WHEN** a client posts valid coordinates and `location_name` `GEC Circle, Chattogram`
- **THEN** the system returns a verification payload including echoed `customer_location` (coordinates, accuracy when provided, location name) and a serviceability decision

#### Scenario: Check without location name still verifies
- **WHEN** a client posts valid latitude/longitude with `location_name` null or omitted
- **THEN** the system still computes serviceability and MUST NOT fail solely because a readable name is missing

#### Scenario: Invalid coordinates rejected
- **WHEN** a client posts malformed or out-of-range latitude/longitude
- **THEN** the system returns `400` or `422` validation errors and does not mark the location as serviceable

### Requirement: Geographic distance matching against active hubs
The system MUST compute geographic distance (Haversine or equivalent) from the customer coordinates to each **active** service hub and treat the customer as serviceable when at least one active hub satisfies `distance_km <= radius_km`. Among covering hubs, the system MUST select the nearest as `matched_service_area`. The system MUST NOT decide serviceability by comparing customer area name to hub name.

#### Scenario: Inside radius is serviceable
- **WHEN** the customer is `3.4` km from an active hub with `radius_km` `5`
- **THEN** the response has `service_available=true` (and `verified=true`) and includes that hub as `matched_service_area` with `distance_km`

#### Scenario: Outside all radii is not serviceable
- **WHEN** the customer is farther than every active hub’s radius
- **THEN** the response has `service_available=false` and includes `nearest_service_area` plus `distance_km` to that nearest active hub when any active hub exists

#### Scenario: Multiple hubs pick nearest covering
- **WHEN** the customer is inside Agrabad (`3.1` km, radius `4`) and outside Chawkbazar (`6.2` km, radius `5`)
- **THEN** `matched_service_area` is Agrabad and `service_available=true`

#### Scenario: No active hubs
- **WHEN** no active hubs exist
- **THEN** the response has `service_available=false` and omits a matched hub (nearest may be absent)

### Requirement: Response separates customer location from matched hub
When serviceable, the response MUST include `customer_location` separately from `matched_service_area` (hub id/public_id, name, radius, and coordinates as documented). When not serviceable, the response MUST include `customer_location` and SHOULD include `nearest_service_area` instead of `matched_service_area`.

#### Scenario: Display name differs from hub name
- **WHEN** customer `location_name` is `GEC Circle, Chattogram` and the covering hub is `Chawkbazar Hub`
- **THEN** the response customer location name remains `GEC Circle, Chattogram` and `matched_service_area.name` is `Chawkbazar Hub`

### Requirement: Accuracy reliability signal
When `accuracy` is provided and exceeds the configured soft threshold (default 500 meters), the system MUST still compute serviceability for history but MUST set `location_reliable=false` and a stable warning code such as `LOW_LOCATION_ACCURACY`. When `accuracy` is omitted (manual pin/search), the system MUST treat the check as reliable for the reliability flag.

#### Scenario: Low accuracy warning
- **WHEN** a client posts `accuracy` of `2500` meters with valid coordinates
- **THEN** the response includes `location_reliable=false` and a low-accuracy warning code while still returning a serviceability computation

#### Scenario: Manual pin without accuracy is reliable
- **WHEN** a client posts coordinates without `accuracy` after a map pin selection
- **THEN** the response sets `location_reliable=true` (or omits unreliability) for the reliability signal

### Requirement: Final serviceability decision is server-side only
The system MUST compute the authoritative `service_available` result on the server. Clients MUST NOT be trusted to assert coverage. Optional client fields claiming serviceability MUST be ignored for authorization of orders or other gated actions.

#### Scenario: Client cannot force serviceable true
- **WHEN** a client sends any client-only flag claiming the area is serviceable while coordinates fall outside all active hubs
- **THEN** the check response still has `service_available=false` and order gates continue to reject that location
