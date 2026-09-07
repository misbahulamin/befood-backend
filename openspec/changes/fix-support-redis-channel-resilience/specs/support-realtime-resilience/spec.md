## ADDED Requirements

### Requirement: Support HTTP APIs survive channel-layer outages

When the Channels Redis backend is unreachable, support inbox HTTP operations that update conversation or message state MUST still complete successfully. Realtime broadcast MUST be best-effort and MUST NOT cause the HTTP request to fail with 500.

#### Scenario: Admin conversation retrieve with Redis down

- **WHEN** an authenticated admin requests `GET /api/v1/web/support/conversations/{public_id}/`
- **AND** the channel layer cannot connect to Redis
- **THEN** the response status is `200`
- **AND** unread messages for that conversation are marked read by admin in the database
- **AND** any broadcast failure is logged without raising to the client

#### Scenario: Message post with Redis down

- **WHEN** an authenticated admin or customer posts a support message via HTTP
- **AND** the channel layer cannot connect to Redis
- **THEN** the message is persisted successfully
- **AND** the HTTP response is a success status for that endpoint
- **AND** broadcast failure does not roll back the persisted message solely due to channel connectivity

### Requirement: Broadcast helpers fail soft

`broadcast_to_conversation` and `broadcast_admin_inbox` MUST catch channel/Redis connectivity errors, log a warning, and return without raising. Non-connectivity errors MUST still propagate.

#### Scenario: group_send raises connection error

- **WHEN** `group_send` raises a Redis or network connection error
- **THEN** the broadcast helper does not raise to the caller
- **AND** a warning is logged that includes enough context to identify the event type

### Requirement: Local channel-layer opt-in is documented and configurable

Local development MUST be able to use Redis (default) or an explicit InMemory channel layer for single-process runs. Documentation MUST state that WebSocket realtime requires a reachable channel backend and that InMemory does not cross processes.

#### Scenario: Local InMemory opt-in

- **WHEN** the local/dev settings enable the InMemory channel layer via the documented env flag
- **THEN** Django uses `channels.layers.InMemoryChannelLayer` for the default channel layer
- **AND** ops documentation describes Redis vs InMemory trade-offs for support chat

#### Scenario: Production remains Redis

- **WHEN** production settings are used without an InMemory override
- **THEN** the default channel layer remains Redis-backed
