# Spec Delta

## MODIFIED Requirements

### Requirement: Push campaign records track admin broadcast lifecycle

The system SHALL persist admin-initiated push broadcasts as `PushCampaign` rows with fields: `public_id` (UUID), `title`, `body`, `notification_type` (enum: `order`, `wallet`, `delivery`, `promotion`, `system`), `data` (JSONField, optional), `created_by` (FK to User), `ip_address` (nullable), `user_agent` (optional), `idempotency_key` (optional), `target_type` (enum: `single_user`, `selected_users`, `filtered_users`, `all_users`), `target_config` (JSONField snapshot), `status` (enum: `pending`, `processing`, `completed`, `failed`), `total_targets`, `total_sent`, `total_failed`, `total_skipped`, `error_summary` (optional), `created_at`, and `updated_at`. The model MUST use `PublicIdMixin`. `total_sent` MUST count only successful FCM deliveries. Dispatch MUST leave every campaign in a terminal `completed` or `failed` status; it MUST NOT remain `processing` after the dispatch attempt ends, including unexpected send errors.

#### Scenario: Campaign created in processing state for async dispatch

- **WHEN** an admin POSTs to the send endpoint with a valid payload
- **THEN** the system creates a `PushCampaign` row with `status=processing` before returning the HTTP response

#### Scenario: Campaign completes with partial failures

- **WHEN** FCM dispatch finishes and 900 of 1000 recipient rows succeed while 100 fail
- **THEN** the campaign `status` MUST be `completed`, `total_sent` MUST be 900, and `total_failed` MUST be 100

#### Scenario: Campaign fails only on unrecoverable errors

- **WHEN** Firebase credentials are missing or an unrecoverable campaign-level error occurs before any send
- **THEN** the campaign `status` MUST be `failed` and `error_summary` MUST describe the failure

#### Scenario: Dispatch exception does not leave processing forever

- **WHEN** dispatch starts and an unexpected send error occurs before completion
- **THEN** the campaign status becomes `failed` or `completed` and MUST NOT remain `processing`

#### Scenario: Zero FCM successes with inbox still counts as completed when no unrecoverable config error

- **WHEN** dispatch finishes with zero FCM successes because all tokens failed or no pending tokens existed, and Firebase was configured
- **THEN** the campaign `status` is `completed`, `total_sent` is `0`, and `total_failed` reflects failed recipients
