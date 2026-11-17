# Spec Delta

## MODIFIED Requirements

### Requirement: Authenticated user can register an FCM device token

The system SHALL expose `POST /notifications/device-token/` for authenticated clients. The endpoint MUST resolve the acting user exclusively from the authentication token (`Authorization: Token <key>`). The request body MUST accept required fields `token` (string, 10–512 chars after trim) and `platform` (enum: `android`, `ios`, `web`). Optional fields `device_name` (max 100 chars) and `app_version` (max 50 chars) MAY be supplied. Unauthenticated callers MUST receive `401`. On success the system MUST respond `200` with `{"success": true, "message": "Device registered successfully"}`.

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

- **WHEN** an authenticated user posts an empty token or a token longer than 512 characters
- **THEN** the system responds `400 Bad Request` with field validation errors

#### Scenario: Long web push token accepted

- **WHEN** an authenticated user posts a `platform=web` token between 256 and 512 characters
- **THEN** the system accepts the token and stores an active device row

#### Scenario: Malicious oversized optional fields rejected

- **WHEN** an authenticated user posts `device_name` longer than 100 characters or `app_version` longer than 50 characters
- **THEN** the system responds `400 Bad Request` with field validation errors
