## ADDED Requirements

### Requirement: Only verified admins can send push notifications

The system SHALL expose `POST /api/v1/web/notifications/send/` restricted to `IsVerifiedAdmin`. Unauthenticated callers MUST receive `401`. Authenticated non-admin users MUST receive `403`.

#### Scenario: Unauthenticated send denied

- **WHEN** an unauthenticated client POSTs to `/api/v1/web/notifications/send/`
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Normal customer cannot send

- **WHEN** an authenticated customer POSTs to the send endpoint
- **THEN** the system responds `403 Forbidden`

#### Scenario: Verified admin receives async acceptance

- **WHEN** a verified admin POSTs a valid send payload
- **THEN** the system responds `202 Accepted` with campaign `public_id`, `status=processing`, and `total_targets`

### Requirement: Send endpoint returns immediately without blocking on FCM

The send endpoint MUST NOT wait for FCM dispatch to complete before returning the HTTP response. The response MUST always be `202 Accepted` for successfully queued campaigns, regardless of target size.

#### Scenario: Large broadcast returns immediately

- **WHEN** an admin sends to 10,000 eligible users
- **THEN** the HTTP response returns within normal API latency with `status=processing` and does not wait for all FCM calls to finish

#### Scenario: Admin polls for completion

- **WHEN** an admin receives a `202` response with `status=processing`
- **THEN** the admin MAY poll `GET /api/v1/web/notifications/{public_id}/` until `status` is `completed` or `failed`

### Requirement: Send endpoint supports idempotency protection

The send endpoint MUST support duplicate prevention via:

1. Optional `Idempotency-Key` request header — same admin + same key within 24 hours MUST return the existing campaign with `202 Accepted` without creating a new campaign
2. Fingerprint dedup — within 5 minutes, identical `title`, `body`, normalized `target`, and `created_by` MUST return `409 Conflict` with the existing campaign `public_id`

#### Scenario: Idempotency-Key prevents duplicate campaign

- **WHEN** an admin sends the same request twice with the same `Idempotency-Key` header
- **THEN** the system creates only one campaign and both responses return the same `public_id` with `202 Accepted`

#### Scenario: Fingerprint dedup blocks rapid duplicate

- **WHEN** an admin sends two identical campaigns within 5 minutes without an idempotency key
- **THEN** the second request responds `409 Conflict` with the first campaign `public_id`

#### Scenario: Duplicate click does not double-send

- **WHEN** an admin double-clicks Send due to slow network and the second request matches the fingerprint dedup window
- **THEN** users MUST NOT receive duplicate push notifications from two campaigns

### Requirement: Send endpoint supports four targeting modes with customer-only validation

The send endpoint MUST accept `target.type` in (`user`, `users`, `filter`, `all`). Every resolved target user MUST have a `CustomerProfile`. Users who are staff, riders, or admins MUST NOT receive customer campaign push.

Allowlisted filter keys: `is_active`, `is_email_verified`, `registered_from`, `registered_to`, `has_active_subscription`, `has_wallet`, `service_area_public_id`.

#### Scenario: Send to single customer user

- **WHEN** admin posts `{"target": {"type": "user", "user_id": 123}}` and user 123 has a `CustomerProfile`
- **THEN** the campaign targets only that customer's active devices

#### Scenario: Staff user cannot be targeted

- **WHEN** admin posts `{"target": {"type": "user", "user_id": 999}}` and user 999 is a staff user without `CustomerProfile`
- **THEN** the system responds `422 Unprocessable Content` indicating the user is not a valid customer target

#### Scenario: Rider user cannot be targeted

- **WHEN** admin posts `{"target": {"type": "user", "user_id": 888}}` and user 888 has only a `RiderProfile`
- **THEN** the system responds `422 Unprocessable Content`

#### Scenario: Admin user cannot be targeted

- **WHEN** admin posts `{"target": {"type": "user", "user_id": 777}}` and user 777 has only an `AdminProfile`
- **THEN** the system responds `422 Unprocessable Content`

#### Scenario: Selected users rejects non-customer IDs

- **WHEN** admin posts `{"target": {"type": "users", "user_ids": [1, 2, 999]}}` and user 999 is not a customer
- **THEN** the system responds `422` listing invalid user IDs

#### Scenario: Send to all users requires confirmation at scale

- **WHEN** admin posts `{"target": {"type": "all"}}` and eligible count exceeds threshold without `confirm_broadcast: true`
- **THEN** the system responds `422 Unprocessable Content`

### Requirement: FCM data payload enforces strict deep-link contract

The `data` field MUST be a JSON object containing only allowlisted keys: `screen`, `entity_type`, `entity_id`. All values MUST be strings. Unknown keys MUST be rejected with `400 Bad Request`. Max serialized size 4 KB.

#### Scenario: Valid deep-link payload accepted

- **WHEN** admin posts `"data": {"screen": "order_detail", "entity_type": "order", "entity_id": "123"}`
- **THEN** the system accepts the payload and forwards it to FCM

#### Scenario: Unknown data key rejected

- **WHEN** admin posts `"data": {"type": "order", "id": "123"}`
- **THEN** the system responds `400 Bad Request` because `type` and `id` are not allowlisted keys

#### Scenario: Non-string data value rejected

- **WHEN** admin posts `"data": {"entity_id": 123}` with a numeric value
- **THEN** the system responds `400 Bad Request`

### Requirement: Send payload validation enforces safe limits

The send endpoint MUST validate: `title` 1–255 chars, `body` 1–4000 chars, `notification_type` in allowed enum, `user_ids` max 500.

#### Scenario: Oversized title rejected

- **WHEN** admin posts a title longer than 255 characters
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin can list push campaign history

The system SHALL expose `GET /api/v1/web/notifications/` for verified admins with pagination. Each item MUST include `public_id`, `title`, `notification_type`, `target_type`, `status`, `total_targets`, `total_sent`, `total_failed`, `total_skipped`, `created_by` (email), and `created_at`.

#### Scenario: Admin lists campaigns paginated

- **WHEN** a verified admin GETs `/api/v1/web/notifications/?page=1&page_size=20`
- **THEN** the system returns a paginated list ordered by newest first

### Requirement: Admin can view campaign delivery detail

The system SHALL expose `GET /api/v1/web/notifications/{public_id}/` including recipient rows with: user email, device platform, status (`sent`/`failed`/`skipped`), `firebase_message_id`, `error_message`, and `sent_at`.

#### Scenario: Admin views partial failure detail

- **WHEN** a campaign has `status=completed` and `total_failed=100`
- **THEN** the detail response includes failed recipients with `error_message` and the campaign remains `completed`

#### Scenario: Campaign not found

- **WHEN** admin GETs a non-existent `public_id`
- **THEN** the system responds `404 Not Found`

### Requirement: Send records broadcast audit metadata

When creating a campaign, the system MUST store `created_by`, client `ip_address`, and `user_agent` from the request for compliance audit.

#### Scenario: Audit fields populated on send

- **WHEN** a verified admin sends a campaign from a browser client
- **THEN** the `PushCampaign` row includes `created_by`, `ip_address`, and `user_agent`

### Requirement: Admin push APIs are documented in OpenAPI

Send, list, and detail endpoints MUST be documented with `@extend_schema`, tags under `Admin Notifications`, and error responses including `409` for duplicate campaigns.

#### Scenario: Swagger shows admin push endpoints

- **WHEN** a developer opens `/api/docs/`
- **THEN** admin notification endpoints appear with schemas, idempotency header, and async 202 examples
