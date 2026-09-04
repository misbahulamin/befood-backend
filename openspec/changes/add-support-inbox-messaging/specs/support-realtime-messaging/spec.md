## ADDED Requirements

### Requirement: Authenticated WebSocket endpoint for a conversation

The system SHALL expose a WebSocket endpoint at `/ws/support/{conversation_public_id}/` (scheme `ws`/`wss` per environment). Connections MUST authenticate with the existing API token mechanism before joining a conversation group. Unauthenticated connections MUST be rejected.

#### Scenario: Valid token connects

- **WHEN** a client connects to `/ws/support/{conversation_public_id}/` with a valid auth token and ACL permission for that conversation
- **THEN** the WebSocket connection is established and the client is subscribed to that conversation's event group

#### Scenario: Missing token rejected

- **WHEN** a client connects without valid authentication
- **THEN** the system MUST reject the WebSocket connection

### Requirement: Real-time message send and receive

The system SHALL accept a client event `message.send` with non-empty body text, persist a `SupportMessage` through the shared support service layer (same rules as REST), update conversation last-message and unread counters, and broadcast `message.receive` to authorized subscribers of that conversation group. Page refresh MUST NOT be required for peers to see the new message when connected.

#### Scenario: Customer message appears instantly for admin

- **WHEN** a connected customer sends `message.send` on their conversation socket
- **THEN** connected authorized admins on that conversation receive `message.receive` containing the persisted message public id, sender type, body, and created_at

#### Scenario: Admin reply appears instantly for customer

- **WHEN** a connected admin sends `message.send` (or equivalent reply event) on a conversation socket
- **THEN** the connected customer on that conversation receives `message.receive` with the admin message payload

#### Scenario: Invalid empty send rejected

- **WHEN** a connected client sends `message.send` with empty body
- **THEN** the system MUST NOT persist a message and MUST notify the sender with an error event or equivalent failure signal

### Requirement: Message read over WebSocket

The system SHALL accept `message.read` from an authorized participant, update the appropriate read flags and unread counters for that side, and broadcast a `message.read` (or equivalent) event to the conversation group so badges can sync.

#### Scenario: Customer marks messages read

- **WHEN** a connected customer sends `message.read` for their conversation
- **THEN** customer-side unread state is cleared or reduced per service rules and peers may receive a read update event

### Requirement: Channel layer backed fan-out

Production and staging deployments that enable WebSockets MUST use a Redis-backed channel layer so multiple ASGI workers can fan out events. Message persistence remains in the primary database.

#### Scenario: Broadcast works across workers

- **WHEN** two authorized clients are connected through different ASGI workers to the same conversation
- **THEN** a message persisted by one client MUST still be delivered to the other via the channel layer

### Requirement: No message delete over WebSocket

The system MUST NOT provide a WebSocket event that deletes support messages from history.

#### Scenario: Delete event unsupported

- **WHEN** a client sends an unsupported delete-message event
- **THEN** the system MUST ignore it or return an error and MUST NOT delete stored messages
