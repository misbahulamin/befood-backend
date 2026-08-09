## ADDED Requirements

### Requirement: Guest check succeeds without Authorization
The public service-area check and demand endpoints MUST allow requests with no `Authorization` header and MUST return a normal coverage JSON response (not an authentication error) when the body contains valid coordinates.

#### Scenario: Anonymous check with coordinates
- **WHEN** a client `POST`s `/api/v1/service-areas/check/` with valid `latitude` and `longitude` and no `Authorization` header
- **THEN** the response status MUST be `200`
- **AND** the body MUST include `service_available` and MUST NOT be `{"detail":"Invalid token."}`

#### Scenario: Anonymous demand with coordinates
- **WHEN** a client `POST`s `/api/v1/service-areas/demand/` with valid coordinates and no `Authorization` header
- **THEN** the response status MUST be `200`
- **AND** a demand history row MUST be recorded

### Requirement: Invalid Authorization does not block public check
When check or demand receives an `Authorization: Token …` value that is missing from the database or otherwise invalid, the system MUST treat the caller as anonymous for that request (or otherwise still complete coverage verification) rather than failing the entire request with only `Invalid token`.

#### Scenario: Stale token on check
- **WHEN** a client `POST`s `/api/v1/service-areas/check/` with a syntactically present but invalid Token header and valid coordinates
- **THEN** coverage verification MUST still complete successfully for the guest path
- **AND** the response MUST NOT be solely `{"detail":"Invalid token."}`

### Requirement: Valid token still attaches customer profile
When check or demand receives a valid customer Token, the system MUST associate the request history with that customer profile.

#### Scenario: Authenticated customer check
- **WHEN** a logged-in customer with a valid Token calls check with valid coordinates
- **THEN** the response MUST succeed
- **AND** the persisted `ServiceAreaRequest` MUST reference that customer profile
