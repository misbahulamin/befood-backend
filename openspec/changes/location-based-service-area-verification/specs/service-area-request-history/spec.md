## ADDED Requirements

### Requirement: Persist every serviceability check
On each successful acceptance of a verification check request (structurally valid coordinates), the system MUST create a `ServiceAreaRequest` history row capturing latitude, longitude, optional accuracy, optional detected location name / formatted address, matched or nearest hub reference when applicable, `distance_km` when computed, `is_serviceable`, request timestamp, and actor identity as user/customer when authenticated or `guest_session_id` when provided for guests.

#### Scenario: Logged-in check stores user reference
- **WHEN** an authenticated customer successfully calls the check API
- **THEN** a history row is stored with that user’s customer/user reference and the computed serviceability fields

#### Scenario: Guest check stores session id
- **WHEN** a guest calls the check API with a `guest_session_id`
- **THEN** a history row is stored with that `guest_session_id` and without requiring login

#### Scenario: Unserviceable checks are still stored
- **WHEN** a check resolves to `service_available=false`
- **THEN** the system still persists the request with `is_serviceable=false` and nearest-hub fields when available

### Requirement: Explicit demand requests
The system SHALL accept an explicit demand action (dedicated endpoint or documented check intent) representing “I want BeFood in my area”. Demand rows MUST be stored with `request_kind=demand` (or equivalent) and the same location fields as checks so non-serviceable demand can be analyzed separately from passive checks.

#### Scenario: Customer saves demand from unavailable state
- **WHEN** a client submits a demand request for coordinates outside all active hubs
- **THEN** the system stores a demand history row with those coordinates and `is_serviceable=false`

#### Scenario: Demand does not grant serviceability
- **WHEN** a demand request is stored for a location
- **THEN** subsequent order creation for that location still requires a normal covering hub match and MUST NOT succeed solely because a demand row exists

### Requirement: History supports expansion analytics inputs
Stored requests MUST be queryable by verified-admin analytics APIs for aggregations such as top requested areas (by detected name or geohash/bucket as implemented) and top non-serviceable locations including request counts and average distance to nearest hub when distance is present.

#### Scenario: Non-serviceable aggregation has counts
- **WHEN** many unserviceable checks exist for detected name `Halishahar`
- **THEN** admin analytics can report `Halishahar` among top non-serviceable locations with a request count greater than zero
