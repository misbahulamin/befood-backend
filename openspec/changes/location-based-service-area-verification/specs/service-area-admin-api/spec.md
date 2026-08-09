## ADDED Requirements

### Requirement: Verified admin service area CRUD API
The system SHALL expose verified-admin web APIs under `/api/v1/web/service-areas/` to list, create, retrieve, update, and delete (or soft-delete) service hubs. List responses MUST be paginated with deterministic ordering. Hub identity in API responses MUST use `public_id`. Unauthenticated or non-admin clients MUST receive `401` or `403`.

#### Scenario: Admin creates hub via web API
- **WHEN** a verified admin `POST`s name, latitude, longitude, and `radius_km` to `/api/v1/web/service-areas/`
- **THEN** the system returns `201 Created` with the hub representation including `public_id`

#### Scenario: Admin lists hubs
- **WHEN** a verified admin `GET`s `/api/v1/web/service-areas/`
- **THEN** the system returns a paginated list including name, coordinates, radius, and active status

#### Scenario: Non-admin denied
- **WHEN** a customer calls admin service-area write endpoints
- **THEN** the system denies access with `401` or `403`

### Requirement: Admin can toggle hub status
The system SHALL allow verified admins to activate or deactivate a hub via PATCH and/or a documented action endpoint. Status changes MUST take effect for subsequent customer verification immediately after commit.

#### Scenario: Deactivate via API
- **WHEN** a verified admin sets a hub’s `is_active` to `false`
- **THEN** customer checks stop matching that hub on the next request

### Requirement: Admin request analytics endpoints
The system SHALL expose verified-admin read APIs for service-area request analytics, including at minimum: top requested areas and top non-serviceable locations with counts (and average distance when available), with allowlisted date filters. Raw request listing MUST be paginated and MUST NOT return unbounded result sets.

#### Scenario: Top non-serviceable summary
- **WHEN** a verified admin requests the non-serviceable summary for a date range that contains Halishahar demand/check traffic
- **THEN** the response includes Halishahar (or its bucket key) with a count and optional average distance metric

#### Scenario: Reject unsupported analytics filters
- **WHEN** a client supplies an unsupported filter field or operator on analytics endpoints
- **THEN** the system responds `400 Bad Request` and does not execute an arbitrary query
