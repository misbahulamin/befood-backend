## ADDED Requirements

### Requirement: Flutter integration guide documents the full device token workflow

The system SHALL include a frontend integration document at `notifications/docs/frontend/fcm-device-token.md` that explains the complete Flutter workflow for a developer with no prior context. The document MUST cover: when to call register (after login and on FCM token refresh), when to call remove (on logout), required headers (`Authorization: Token <key>`, optional `X-Client-Type: mobile`), base path, request/response JSON for both endpoints, field meanings, and error handling.

#### Scenario: Developer can integrate from docs alone

- **WHEN** a Flutter developer reads `notifications/docs/frontend/fcm-device-token.md`
- **THEN** they can implement register-on-login, refresh-on-token-change, and remove-on-logout without reading backend source code

#### Scenario: Docs include request examples

- **WHEN** the frontend doc describes the register endpoint
- **THEN** it includes a complete JSON request example with `token`, `platform`, and optional `device_name`/`app_version`

#### Scenario: Docs include error scenarios

- **WHEN** the frontend doc describes error handling
- **THEN** it documents `401` (not logged in), `400` (validation), and expected success response shapes

### Requirement: Backend technical documentation covers device token management

The system SHALL include a backend document at `notifications/docs/backend/fcm-device-token.md` covering model fields, indexes, service functions, API endpoints, migration notes, and how future FCM send integration should consume query helpers.

#### Scenario: Backend doc explains indexing decisions

- **WHEN** a backend developer reads `notifications/docs/backend/fcm-device-token.md`
- **THEN** they understand why composite `(user, is_active)` and unique `token` indexes exist

#### Scenario: Backend doc documents ownership transfer behavior

- **WHEN** a backend developer reads the ownership transfer section
- **THEN** they understand why token reassignment on login is intentional and how it affects the previous user
