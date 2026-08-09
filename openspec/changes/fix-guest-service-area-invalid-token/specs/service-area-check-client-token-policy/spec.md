## ADDED Requirements

### Requirement: Guest check requests omit Authorization
The customer frontend service-area check/demand client MUST NOT send an `Authorization` header when the user has no active customer login token.

#### Scenario: No token in storage
- **WHEN** the Delivery box runs location check and `localStorage` has no customer auth token
- **THEN** the request to `/api/v1/service-areas/check/` MUST omit `Authorization`
- **AND** MUST still send `X-Guest-Session-Id` (and optional `X-Client-Type`)

### Requirement: Stale token recovery for check and demand
If check or demand fails because of an invalid customer token, the frontend MUST clear the stale token and retry once without `Authorization` so the guest coverage flow can succeed.

#### Scenario: Garbage token in localStorage
- **WHEN** `localStorage` contains a non-empty customer token that the backend rejects as invalid
- **AND** the user triggers service-area check
- **THEN** the client MUST recover (clear token and/or retry without Authorization)
- **AND** the user MUST see a successful coverage result or a domain/UI error other than a permanent `Invalid token` dead-end

### Requirement: Valid session may attach Authorization
When the customer is logged in with a token the app considers active, check/demand MAY send `Authorization: Token …` so the backend can store `customer_profile` on the history row.

#### Scenario: Logged-in customer check
- **WHEN** the customer has a valid login session
- **AND** they run location check
- **THEN** the client MAY include `Authorization`
- **AND** MUST still include guest session headers only as required by the public contract (guest id optional when authenticated)

### Requirement: Free map stack is unrelated to Invalid token
The frontend MUST keep using the free geocoding/map stack (Nominatim + Leaflet/OSM by default) for location name and map pin UX; documentation MUST state that `{"detail":"Invalid token."}` comes from BeFood auth headers, not from Nominatim or map tiles.

#### Scenario: Reverse geocode succeeds while check fails
- **WHEN** Nominatim reverse geocode succeeds and BeFood check fails with Invalid token before the fix
- **THEN** engineers MUST treat the failure as auth-client policy, not as a missing paid map API key
- **AND** the product MUST NOT require a paid map provider to fix this error
