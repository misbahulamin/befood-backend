## ADDED Requirements

### Requirement: Admin can list support conversations

The system SHALL provide a verified-admin web API at `GET /api/v1/web/support/conversations/` that returns a paginated list of customer support conversations. Each list item MUST include at least: conversation `public_id`, customer display name, phone, email (nullable if absent), last message preview, last message time, admin unread count, and conversation status (`open`, `closed`, or `archived`). The list contract MUST allow clients to display online status when presence data is available (field may be computed/ephemeral, not necessarily a DB column). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`. Ordering MUST prefer most recent activity with a unique tie-breaker.

#### Scenario: Verified admin lists conversations

- **WHEN** a verified admin requests `GET /api/v1/web/support/conversations/`
- **THEN** the system responds `200` with a paginated list including the required customer and last-message fields

#### Scenario: Non-admin denied

- **WHEN** an authenticated customer without verified-admin permission requests the admin conversation list
- **THEN** the system responds `403 Forbidden`

### Requirement: Admin conversation filters and search

The system SHALL support allowlisted filters for conversation `status` and admin unread (e.g. `has_unread=true`), and MUST support search `q` against customer name, phone, or email. Unknown filter keys MUST be rejected with `400` when validation is enabled.

#### Scenario: Filter by open status

- **WHEN** a verified admin lists conversations with `status=open`
- **THEN** only conversations with status `open` MUST be returned

#### Scenario: Filter unread conversations

- **WHEN** a verified admin lists conversations with an unread filter enabled
- **THEN** only conversations with admin unread count greater than zero MUST be returned

#### Scenario: Search by phone

- **WHEN** a verified admin lists conversations with `q` matching a customer phone
- **THEN** conversations for matching customers MUST be included in the result set

### Requirement: Admin can view conversation detail and history

The system SHALL provide `GET /api/v1/web/support/conversations/{public_id}/` for verified admins to retrieve conversation metadata, customer info, and paginated message history. Missing conversations MUST return `404`. Opening detail MUST clear or reduce admin unread for that conversation per documented read rules.

#### Scenario: Admin opens a conversation

- **WHEN** a verified admin requests detail for an existing conversation public id
- **THEN** the system responds `200` with customer info and message history including customer and admin messages

### Requirement: Admin can reply via REST

The system SHALL provide `POST /api/v1/web/support/conversations/{public_id}/reply/` for verified admins to append an `admin` message, update last-message metadata and customer unread, and broadcast to the conversation WebSocket group when available. Empty text MUST be rejected. No normal admin delete-message API.

#### Scenario: Admin sends a reply

- **WHEN** a verified admin posts a valid reply to an existing conversation
- **THEN** the system responds with success (`201` preferred), stores the message permanently, and attempts real-time broadcast to authorized subscribers

### Requirement: Admin can update conversation status

The system SHALL provide `PATCH /api/v1/web/support/conversations/{public_id}/status/` (or equivalent documented body on PATCH) allowing status `open`, `closed`, or `archived`. Invalid values MUST be rejected.

#### Scenario: Admin closes a conversation

- **WHEN** a verified admin sets status to `closed` on an existing conversation
- **THEN** subsequent list/detail responses MUST show status `closed`

### Requirement: Admin participates in live conversation over WebSocket

A verified admin SHALL be allowed to connect to a conversation WebSocket by `public_id` and to receive live message, typing, presence, and read events. Non-admin users MUST NOT use admin-only inbox broadcast groups.

#### Scenario: Admin joins conversation socket

- **WHEN** a verified admin opens a WebSocket to an existing conversation public id with a valid token
- **THEN** the connection is accepted and they receive live `message.receive` events for that conversation

#### Scenario: Customer cannot use admin list privileges over WS

- **WHEN** an authenticated customer connects to WebSocket
- **THEN** they MUST NOT receive other customers' conversation events or admin-wide inbox streams
