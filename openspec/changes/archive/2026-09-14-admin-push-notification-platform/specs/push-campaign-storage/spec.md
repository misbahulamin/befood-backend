## ADDED Requirements

### Requirement: Push campaign records track admin broadcast lifecycle

The system SHALL persist admin-initiated push broadcasts as `PushCampaign` rows with fields: `public_id` (UUID), `title`, `body`, `notification_type` (enum: `order`, `wallet`, `delivery`, `promotion`, `system`), `data` (JSONField, optional), `created_by` (FK to User), `ip_address` (nullable), `user_agent` (optional), `idempotency_key` (optional), `target_type` (enum: `single_user`, `selected_users`, `filtered_users`, `all_users`), `target_config` (JSONField snapshot), `status` (enum: `pending`, `processing`, `completed`, `failed`), `total_targets`, `total_sent`, `total_failed`, `total_skipped`, `error_summary` (optional), `created_at`, and `updated_at`. The model MUST use `PublicIdMixin`.

#### Scenario: Campaign created in processing state for async dispatch

- **WHEN** an admin POSTs to the send endpoint with a valid payload
- **THEN** the system creates a `PushCampaign` row with `status=processing` before returning the HTTP response

#### Scenario: Campaign completes with partial failures

- **WHEN** FCM dispatch finishes and 900 of 1000 recipient rows succeed while 100 fail
- **THEN** the campaign `status` MUST be `completed`, `total_sent` MUST be 900, and `total_failed` MUST be 100

#### Scenario: Campaign fails only on unrecoverable errors

- **WHEN** Firebase credentials are missing or an unrecoverable campaign-level error occurs before any send
- **THEN** the campaign `status` MUST be `failed` and `error_summary` MUST describe the failure

### Requirement: Push campaign recipient records track per-user delivery with skipped status

The system SHALL persist delivery rows as `PushCampaignRecipient` with fields: `campaign` (FK), `user` (FK), `device` (FK to `DeviceToken`, nullable), `status` (enum: `pending`, `sent`, `failed`, `skipped`), `firebase_message_id` (optional), `error_message` (optional), and `sent_at` (nullable). One recipient row MUST exist per (user, active device) pair when the user is eligible for push.

#### Scenario: User with two active devices gets two recipient rows

- **WHEN** a campaign targets a user who has two active `DeviceToken` rows and push is enabled
- **THEN** the system creates two `PushCampaignRecipient` rows with `status=pending` initially

#### Scenario: User without active device gets failed recipient row

- **WHEN** a campaign targets a user with no active device tokens
- **THEN** the system creates one recipient row with `status=failed` and an error message indicating no active device

#### Scenario: Opted-out user gets skipped recipient row

- **WHEN** a campaign targets a user with `NotificationPreference.push_enabled=False`
- **THEN** the system creates a recipient row with `status=skipped` and MUST increment `PushCampaign.total_skipped` (not `total_failed`)

### Requirement: Push campaign models have optimized indexes

The system MUST define database indexes supporting: campaign history by status and date, recipient lookup by campaign and status, and idempotency key lookup by admin.

#### Scenario: Campaign list query uses status index

- **WHEN** an admin lists campaigns filtered by `status=completed`
- **THEN** the query MUST use an index on `(status, created_at)` or equivalent composite index

#### Scenario: Idempotency key lookup is efficient

- **WHEN** a send request includes an `Idempotency-Key` header reused by the same admin
- **THEN** the system MUST look up the existing campaign via indexed `idempotency_key` and `created_by`

### Requirement: Future retry fields are reserved in design

The design MUST document future recipient fields `retry_count`, `last_error`, and `next_retry_at` for transient FCM failure retry. MVP implementation MAY omit these columns but MUST NOT design recipient status logic that prevents adding them later.

#### Scenario: Transient FCM failure recorded as failed in MVP

- **WHEN** FCM returns a transient network error during MVP dispatch
- **THEN** the recipient `status` is `failed` with `error_message` describing the error, and a future retry worker can re-process using reserved field design
