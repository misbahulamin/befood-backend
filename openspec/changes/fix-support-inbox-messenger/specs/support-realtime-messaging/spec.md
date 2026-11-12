# Spec Delta

## ADDED Requirements

### Requirement: Authenticated admin inbox WebSocket

The system SHALL expose a WebSocket endpoint at `/ws/support/inbox/` (scheme `ws`/`wss` per environment) for verified admins only. Successful connections MUST subscribe to the admin inbox broadcast group and receive existing support inbox fan-out events including at least `conversation.updated` (and message/typing events when forwarded to that group). Unauthenticated connections MUST be rejected. Authenticated non-admin connections MUST be rejected (close code `4403` preferred). The per-conversation WebSocket at `/ws/support/{conversation_public_id}/` MUST remain available and unchanged in ACL for conversation participants.

#### Scenario: Verified admin joins inbox socket

- **WHEN** a verified admin connects to `/ws/support/inbox/` with a valid auth token
- **THEN** the connection is accepted and the admin is subscribed to the admin inbox event group

#### Scenario: Non-admin rejected from inbox socket

- **WHEN** an authenticated customer connects to `/ws/support/inbox/`
- **THEN** the system MUST reject the connection and MUST NOT subscribe them to the admin inbox group

#### Scenario: Inbox receives conversation.updated without open conversation

- **WHEN** a customer posts a new support message while a verified admin is connected only to `/ws/support/inbox/` (no conversation socket open)
- **THEN** that admin MUST receive a `conversation.updated` event with the updated conversation summary within normal realtime delivery latency

### Requirement: Conversation summary includes sender and avatar for inbox

Admin inbox `conversation.updated` payloads MUST include `last_message_sender` (`customer`, `admin`, or null) and the customer's `profile_picture_url` (nullable) alongside existing summary fields so clients can render Messenger-style previews without an extra fetch.

#### Scenario: Summary after customer message

- **WHEN** a customer message updates a conversation and the admin inbox is broadcast
- **THEN** the `conversation.updated` payload MUST include `last_message_sender` equal to `customer` and a `customer` object that includes `profile_picture_url`

## MODIFIED Requirements

### Requirement: Real-time message send and receive

The system SHALL accept a client event `message.send` with non-empty body text, persist a `SupportMessage` through the shared support service layer (same rules as REST), update conversation last-message and unread counters, and broadcast `message.receive` to authorized subscribers of that conversation group. Page refresh MUST NOT be required for peers to see the new message when connected. Every successful customer or admin message persistence path (REST and WebSocket) that updates last-message metadata MUST also broadcast `conversation.updated` to the admin inbox group with the updated conversation summary.

#### Scenario: Customer message appears instantly for admin

- **WHEN** a connected customer sends `message.send` on their conversation socket
- **THEN** connected authorized admins on that conversation receive `message.receive` containing the persisted message public id, sender type, body, and created_at

#### Scenario: Admin reply appears instantly for customer

- **WHEN** a connected admin sends `message.send` (or equivalent reply event) on a conversation socket
- **THEN** the connected customer on that conversation receives `message.receive` with the admin message payload

#### Scenario: Invalid empty send rejected

- **WHEN** a connected client sends `message.send` with empty body
- **THEN** the system MUST NOT persist a message and MUST notify the sender with an error event or equivalent failure signal

#### Scenario: Customer message fans out to admin inbox group

- **WHEN** a customer message is persisted via REST or WebSocket
- **THEN** the system MUST broadcast `conversation.updated` to the admin inbox group with the updated summary
