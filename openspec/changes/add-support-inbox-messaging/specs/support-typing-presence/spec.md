## ADDED Requirements

### Requirement: Typing indicators are ephemeral WebSocket events

The system SHALL support `typing.start` and `typing.stop` events on the conversation WebSocket. Typing state MUST NOT be written to the durable support message tables. Peers in the conversation group MUST receive typing events so UIs can show “Admin is typing…” / “Customer is typing…”. When typing stops (explicit `typing.stop` or client-side timeout), the indicator MUST be clearable without a page refresh.

#### Scenario: Customer typing visible to admin

- **WHEN** a connected customer sends `typing.start` on their conversation socket
- **THEN** connected authorized admins on that conversation receive `typing.start` for the customer side

#### Scenario: Typing stop clears indicator

- **WHEN** that customer sends `typing.stop` (or the client timeout elapses and stop is signaled)
- **THEN** peers receive `typing.stop` and MUST NOT rely on a database row for typing state

#### Scenario: Typing not stored as messages

- **WHEN** typing events are exchanged
- **THEN** no new `SupportMessage` rows are created for typing

### Requirement: Online and offline presence via connection lifecycle

The system SHALL derive online/offline presence from WebSocket connect/disconnect (and optional heartbeat), preferably stored in Redis/cache with TTL—not as a permanent column on `SupportConversation`. The system SHALL broadcast `presence.online` and `presence.offline` to relevant subscribers so:

- Admin conversation list/chat can show customer online status
- Customer chat can show support-agent online status per documented presence rules

#### Scenario: Customer comes online

- **WHEN** an authenticated customer successfully connects to their support conversation WebSocket
- **THEN** authorized admin subscribers MAY receive `presence.online` for that customer

#### Scenario: Customer goes offline

- **WHEN** that customer disconnects from the WebSocket
- **THEN** authorized admin subscribers MAY receive `presence.offline` for that customer

#### Scenario: Presence not permanent in conversation row

- **WHEN** presence changes
- **THEN** the system MUST NOT require a durable “is_online” field on `SupportConversation` as source of truth

### Requirement: Presence does not replace authentication

Presence signals MUST only be emitted for authenticated, ACL-authorized connections. Presence MUST NOT grant access to message history by itself.

#### Scenario: Unauthenticated user has no presence

- **WHEN** an unauthenticated client fails WebSocket auth
- **THEN** no `presence.online` event is published for that attempt
