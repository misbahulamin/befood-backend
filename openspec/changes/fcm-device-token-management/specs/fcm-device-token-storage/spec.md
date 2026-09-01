## ADDED Requirements

### Requirement: DeviceToken model stores FCM tokens with integrity constraints

The system SHALL store FCM device tokens in the existing `DeviceToken` model (`user_management.models.DeviceToken`). Each row MUST include: `id`, `user` (FK to `auth.User`), `token`, `platform`, `device_name` (optional, blank allowed), `app_version` (optional, blank allowed), `is_active`, `last_used_at`, `created_at`, `updated_at`. The `token` field MUST be globally unique across all rows. One user MAY have multiple device rows. Duplicate token values MUST NOT be permitted at the database level.

#### Scenario: Unique token constraint enforced

- **WHEN** the database receives two insert attempts with the same `token` value
- **THEN** the second insert MUST fail with an integrity error

#### Scenario: User can have multiple devices

- **WHEN** a user registers two different FCM tokens
- **THEN** both rows exist linked to the same user with distinct token values

### Requirement: DeviceToken indexes optimize high-traffic queries

The system MUST maintain a composite index on `(user, is_active)` for the query pattern `filter(user=user, is_active=True)`. The `token` column MUST have a unique index (via unique constraint). Standalone indexes on `user` or `is_active` alone MUST NOT be added when the composite index sufficiently covers the primary access patterns.

#### Scenario: Active tokens for user query uses composite index

- **WHEN** `get_user_device_tokens(user)` executes
- **THEN** the queryset filters on `user` and `is_active=True` and MUST NOT load unnecessary related objects

#### Scenario: Lookup by token uses unique index

- **WHEN** the register service looks up a row by exact `token`
- **THEN** the query uses the unique token index

### Requirement: Migration deduplicates existing tokens before unique constraint

If duplicate `token` values exist in production data before this change, the migration MUST deduplicate by retaining the row with the most recent `created_at` (or `last_used_at` when present) and removing or deactivating other duplicates before applying the unique constraint.

#### Scenario: Pre-existing duplicates cleaned

- **WHEN** the migration runs on a database with duplicate token rows
- **THEN** only one row per token remains and the unique constraint applies successfully

### Requirement: Platform field uses documented enum values

The `platform` field MUST accept only documented values: `android`, `ios`, `web`. Validation MUST occur at the API serializer layer; the model MAY store as CharField with choices.

#### Scenario: Valid platform stored

- **WHEN** a device is registered with `platform=android`
- **THEN** the row stores `android` as the platform value
