## ADDED Requirements

### Requirement: Service-area check remains backward compatible
The system MUST preserve existing request fields and existing response fields for `POST /api/v1/service-areas/check/` (`verified`, `service_available`, `location_reliable`, `customer_location`, `distance_km`, `matched_service_area` / `nearest_service_area`, warning fields). Existing clients MUST continue to succeed without sending new fields.

#### Scenario: Legacy guest check unchanged
- **WHEN** a guest posts latitude, longitude, and guest_session_id as today
- **THEN** the system returns the existing verification payload shape and persists a ServiceAreaRequest

### Requirement: Authenticated check may include saved_location hint
When the caller is an authenticated customer, the check response MAY include an additive `saved_location` object with at least `exists` (boolean) and, when a linked active delivery place exists, `address_id` (place `public_id`) and a freshness indicator (`stale` or equivalent). The hint refers to the **saved** delivery place, not last-detected-only GPS. Existing accuracy behavior (`LOW_LOCATION_ACCURACY` when accuracy exceeds threshold) MUST remain unchanged. Unauthenticated responses MUST omit `saved_location` or set `exists=false` without breaking parsers that ignore unknown keys.

#### Scenario: Authenticated customer with active place
- **WHEN** a logged-in customer with an active location preference linked to a place calls check
- **THEN** the response includes existing fields plus `saved_location.exists=true` and that place’s `address_id`

#### Scenario: Guest response has no saved place
- **WHEN** a guest calls check
- **THEN** existing fields are present and no customer delivery place is implied as saved
