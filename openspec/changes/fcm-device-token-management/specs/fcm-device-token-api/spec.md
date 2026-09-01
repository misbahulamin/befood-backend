## ADDED Requirements

### Requirement: Authenticated user can register an FCM device token

The system SHALL expose `POST /notifications/device-token/` for authenticated clients. The endpoint MUST resolve the acting user exclusively from the authentication token (`Authorization: Token <key>`). The request body MUST accept required fields `token` (string, 10–255 chars after trim) and `platform` (enum: `android`, `ios`, `web`). Optional fields `device_name` (max 100 chars) and `app_version` (max 50 chars) MAY be supplied. Unauthenticated callers MUST receive `401`. On success the system MUST respond `200` with `{"success": true, "message": "Device registered successfully"}`.

#### Scenario: Unauthenticated register denied

- **WHEN** an unauthenticated client posts to `/notifications/device-token/`
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Authenticated user registers new token

- **WHEN** an authenticated user posts a valid token and platform that does not exist in the database
- **THEN** the system creates a new active `DeviceToken` row linked to that user and responds `200` with success message

#### Scenario: Same user re-registers existing token

- **WHEN** an authenticated user posts a token that already exists for the same user
- **THEN** the system MUST NOT create a duplicate row, MUST set `is_active=True`, MUST update `last_used_at`, and MUST respond `200`

#### Scenario: Token exists for different user — ownership transfer

- **WHEN** an authenticated user posts a token that exists for a different user
- **THEN** the system MUST reassign the row to the authenticated user, set `is_active=True`, update timestamps, and respond `200`

#### Scenario: Invalid platform rejected

- **WHEN** an authenticated user posts with `platform` not in the allowlist
- **THEN** the system responds `400 Bad Request` with field validation errors

#### Scenario: Empty or oversized token rejected

- **WHEN** an authenticated user posts an empty token or a token longer than 255 characters
- **THEN** the system responds `400 Bad Request` with field validation errors

#### Scenario: Malicious oversized optional fields rejected

- **WHEN** an authenticated user posts `device_name` longer than 100 characters or `app_version` longer than 50 characters
- **THEN** the system responds `400 Bad Request` with field validation errors

### Requirement: Authenticated user can deactivate their device token

The system SHALL expose `POST /notifications/device-token/remove/` for authenticated clients. The request body MUST include `token` (the FCM token to deactivate). The system MUST set `is_active=False` on the matching row only when it belongs to the authenticated user. The row MUST NOT be deleted. Unauthenticated callers MUST receive `401`. On success the system MUST respond `200` with `{"success": true, "message": "Device deactivated successfully"}`.

#### Scenario: Unauthenticated remove denied

- **WHEN** an unauthenticated client posts to `/notifications/device-token/remove/`
- **THEN** the system responds `401 Unauthorized`

#### Scenario: User deactivates own token

- **WHEN** an authenticated user posts their own active token to the remove endpoint
- **THEN** the system sets `is_active=False` on that row and responds `200` with success message

#### Scenario: User cannot deactivate another user's token

- **WHEN** an authenticated user posts a token that belongs to a different user
- **THEN** the system responds `404 Not Found` (or `403 Forbidden`) without modifying the other user's row

#### Scenario: Remove idempotent for already inactive token

- **WHEN** an authenticated user posts a token they own that is already inactive
- **THEN** the system responds `200` with success message and the row remains inactive

#### Scenario: Remove unknown token

- **WHEN** an authenticated user posts a token that does not exist in the database
- **THEN** the system responds `404 Not Found`

### Requirement: Device token API is documented in OpenAPI

The register and remove endpoints MUST be documented with `@extend_schema` including request/response examples, authentication requirement, and tags under `Notifications`. Schema generation MUST succeed without warnings for these endpoints.

#### Scenario: Swagger shows device token endpoints

- **WHEN** a developer opens `/api/docs/` after deployment
- **THEN** both device token endpoints appear under the Notifications tag with request body schemas and success response examples
