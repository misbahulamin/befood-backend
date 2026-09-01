## ADDED Requirements

### Requirement: Firebase Admin SDK initializes from settings with multi-process safety

The system SHALL initialize the Firebase Admin SDK using `django.conf.settings.FIREBASE_CREDENTIALS`. Before calling `initialize_app()`, the system MUST call `firebase_admin.get_app()` and only initialize when no app exists. Credentials MUST NOT be hardcoded.

#### Scenario: Firebase initializes once per process

- **WHEN** `FIREBASE_CREDENTIALS` points to a valid service account JSON file and no Firebase app exists in the process
- **THEN** the first send call initializes the Firebase app exactly once

#### Scenario: Multi-worker process reuses existing Firebase app

- **WHEN** a send helper is called and `firebase_admin.get_app()` succeeds because another import already initialized the app
- **THEN** the system MUST reuse the existing app and MUST NOT raise "Firebase app already exists"

#### Scenario: Missing credentials fail gracefully

- **WHEN** dispatch runs and Firebase credentials are not configured
- **THEN** the campaign MUST transition to `failed` with a safe `error_summary` and no internal path in the API response

### Requirement: FCM send helpers support single and batch delivery

The system SHALL provide `send_to_token()` and `send_to_tokens()` in `notifications/services/fcm_service.py`. Batch sends MUST respect the FCM multicast limit of 500 tokens per batch.

#### Scenario: Batch send chunks large token lists

- **WHEN** 1200 active tokens are submitted for send
- **THEN** the system MUST perform at least 3 FCM batch calls (500 + 500 + 200)

#### Scenario: Successful send returns message identifier

- **WHEN** FCM accepts a message for a valid token
- **THEN** the send result MUST include a Firebase message identifier stored on the recipient row

### Requirement: Invalid FCM tokens are deactivated automatically

When Firebase returns an invalid or unregistered registration token error, the system MUST soft-deactivate the corresponding `DeviceToken` row and mark the recipient `status=failed`.

#### Scenario: Unregistered token deactivated

- **WHEN** FCM returns an unregistered/invalid token error for a device
- **THEN** the system sets `DeviceToken.is_active=False` and marks the recipient `status=failed`

### Requirement: Send logic stays out of views

Firebase sending logic MUST reside exclusively in `notifications/services/fcm_service.py` and `notification_sender.py`. API views MUST NOT import `firebase_admin` directly.

#### Scenario: View enqueues dispatch without blocking

- **WHEN** an admin POSTs to the send endpoint
- **THEN** the view MUST create the campaign and enqueue dispatch without awaiting FCM completion

### Requirement: Dispatch entry point supports management command

The system MUST provide `python manage.py dispatch_push_campaign` that calls the same `dispatch_push_campaign(campaign_id)` service function used by the in-process thread dispatcher. The command MUST support processing stuck `processing` campaigns via a `--stuck-only` flag.

#### Scenario: Management command dispatches a campaign

- **WHEN** an operator runs `manage.py dispatch_push_campaign --campaign-id=<public_id>`
- **THEN** the system executes FCM dispatch and updates campaign and recipient statuses

#### Scenario: Stuck campaigns are recoverable

- **WHEN** a process restart leaves campaigns in `processing` status
- **THEN** `manage.py dispatch_push_campaign --stuck-only` MUST resume or complete those campaigns
