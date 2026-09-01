## ADDED Requirements

### Requirement: Frontend admin documentation covers complete push notification workflow

The system SHALL provide frontend documentation at `notifications/docs/frontend/admin-push-notifications.md` covering authentication, send page, history list, detail page, async polling, and deep-link payload integration for Flutter.

#### Scenario: Documentation describes async send workflow

- **WHEN** a frontend developer reads the admin push documentation
- **THEN** they find numbered steps: compose → POST /send/ (202) → poll detail until completed → show results

#### Scenario: Documentation includes request and response examples

- **WHEN** a frontend developer reads the documentation
- **THEN** each API endpoint includes example JSON, HTTP status codes, and field meanings including `total_skipped`

### Requirement: Frontend documentation specifies Notification List page

The documentation MUST specify a Notification List page with columns: Title, Type (notification_type), Target (target_type label), Status, Sent (`total_sent`), Failed (`total_failed`), Skipped (`total_skipped`), Created By, Date (`created_at`). The list MUST support pagination and filters by status and notification_type.

#### Scenario: List page column contract documented

- **WHEN** a developer implements the notification history table
- **THEN** the documentation defines each column's data source field and display format (e.g. status badge colors for `processing`, `completed`, `failed`)

#### Scenario: Partial failure visible in list

- **WHEN** a campaign has `status=completed` and `total_failed > 0`
- **THEN** the documentation explains the UI MUST show failed count prominently without treating the campaign as fully failed

### Requirement: Frontend documentation specifies Send page

The documentation MUST specify a Send page with fields:

- Title (text input, max 255)
- Body (textarea, max 4000)
- Notification Type (select: order, wallet, delivery, promotion, system)
- Target mode (radio/tabs): Single user search, Multiple users multi-select, Filter builder, All users broadcast
- Deep-link data fields: Screen, Entity Type, Entity ID (with Flutter routing examples)
- Broadcast confirmation dialog when eligible count exceeds threshold
- Preview panel showing title, body, estimated target count before send
- Idempotency-Key generation (client UUID per send attempt)
- Disable Send button after click until 202 response received

#### Scenario: Single user search documented

- **WHEN** a developer implements single-user targeting
- **THEN** the documentation describes reusing admin customer search to resolve `user_id` and validating customer-only selection

#### Scenario: Filter builder documented with allowlist

- **WHEN** a developer implements filter targeting
- **THEN** the documentation lists every supported filter key, type, and example values matching the backend allowlist

#### Scenario: Preview panel documented

- **WHEN** an admin fills the send form
- **THEN** the documentation describes a client-side preview showing notification title/body and optional estimated recipient count before confirmation

#### Scenario: Broadcast confirmation dialog documented

- **WHEN** eligible user count exceeds the broadcast threshold
- **THEN** the documentation describes a confirmation modal requiring explicit admin acknowledgment before setting `confirm_broadcast: true`

### Requirement: Frontend documentation specifies Detail page

The documentation MUST specify a Campaign Detail page showing:

- Campaign info: title, body, type, target type, status, all counters (sent/failed/skipped), created by, created date
- Recipients table: user email, device platform, status badge (`sent`/`failed`/`skipped`), failed reason (`error_message`), Firebase message ID, sent timestamp
- Status polling while `processing`: poll `GET /{public_id}/` every 2–3 seconds until terminal state
- Summary chips: sent count, failed count, skipped count

#### Scenario: Skipped recipients displayed distinctly

- **WHEN** a detail page shows recipients with `status=skipped`
- **THEN** the documentation specifies a distinct UI treatment (not red/error styling) with label "Push disabled by user"

#### Scenario: Failed recipients show Firebase error

- **WHEN** a recipient has `status=failed`
- **THEN** the detail page MUST display `error_message` and `firebase_message_id` when present

### Requirement: Frontend documentation covers Flutter deep-link payload contract

The documentation MUST explain how Flutter apps consume FCM `data` payload keys (`screen`, `entity_type`, `entity_id`) for navigation, with examples per notification type.

#### Scenario: Order notification routing example

- **WHEN** a developer reads the Flutter integration section
- **THEN** they find an example: `{"screen": "order_detail", "entity_type": "order", "entity_id": "123"}` navigates to order detail screen

### Requirement: Backend technical documentation covers admin push APIs

The system SHALL provide backend documentation at `notifications/docs/backend/admin-push-notifications.md` with endpoint grid, permissions matrix, async dispatch flow, idempotency rules, partial failure semantics, management command usage, and Firebase setup.

#### Scenario: Backend doc explains partial failure semantics

- **WHEN** a backend developer reads the technical documentation
- **THEN** they find explicit guidance that `status=completed` with `total_failed > 0` means partial delivery errors, not campaign failure

#### Scenario: Backend doc documents management command

- **WHEN** a developer deploys to production
- **THEN** the documentation includes cron setup for `manage.py dispatch_push_campaign --stuck-only`
