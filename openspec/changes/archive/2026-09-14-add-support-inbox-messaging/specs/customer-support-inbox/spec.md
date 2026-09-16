## ADDED Requirements

### Requirement: Customer can view own support inbox

The system SHALL provide an authenticated customer endpoint `GET /api/v1/support/inbox/` that returns the caller's single support conversation metadata (including unread count and status) and a paginated message history. Unauthenticated callers MUST receive `401`. Authenticated users without a customer profile MUST receive `403`. The endpoint MUST NOT return another customer's conversation. Message history MUST be ordered by `created_at` ascending with a unique tie-breaker. Collections MUST be paginated with a documented default and maximum page size.

#### Scenario: Customer opens empty inbox

- **WHEN** an authenticated customer with a profile requests `GET /api/v1/support/inbox/` and no conversation exists yet
- **THEN** the system get-or-creates their conversation and responds `200` with conversation metadata and an empty paginated message list

#### Scenario: Customer sees prior messages and admin replies

- **WHEN** an authenticated customer requests `GET /api/v1/support/inbox/` and messages from both customer and admin exist
- **THEN** the system responds `200` including those messages in chronological order with sender type distinguishable

#### Scenario: Unauthenticated inbox denied

- **WHEN** an unauthenticated client requests `GET /api/v1/support/inbox/`
- **THEN** the system responds `401 Unauthorized`

### Requirement: Customer can send a support message via REST fallback

The system SHALL provide `POST /api/v1/support/messages/` for an authenticated customer to append a message to their support conversation when WebSocket send is unavailable or as an alternate path. The body MUST include non-empty message text. The system MUST persist with sender type `customer`, update last-message metadata and admin unread, and fan out to the conversation WebSocket group when the channel layer is available. Empty text MUST be rejected. The system MUST NOT provide a customer API to delete messages.

#### Scenario: Customer sends a message via REST

- **WHEN** an authenticated customer posts a valid message to `POST /api/v1/support/messages/`
- **THEN** the system responds with success (`201` preferred), stores the message permanently, and attempts real-time broadcast to authorized conversation subscribers

#### Scenario: Empty message rejected

- **WHEN** an authenticated customer posts an empty or whitespace-only message
- **THEN** the system rejects the request with a validation error and does not create a message row

### Requirement: One conversation per customer

The system SHALL enforce at most one support conversation per customer profile. Repeated inbox opens and message posts MUST reuse the same conversation `public_id`.

#### Scenario: Second message reuses conversation

- **WHEN** the same customer sends two messages on different requests
- **THEN** both messages belong to the same conversation public id

### Requirement: Messages are permanent

The system MUST NOT expose customer HTTP APIs that delete support messages. Prior messages MUST remain readable after later messages are posted.

#### Scenario: History retained after new messages

- **WHEN** a customer has previously sent messages and later sends another message
- **THEN** earlier messages MUST still appear in the inbox history response

### Requirement: Customer participates in live conversation over WebSocket

An authenticated customer SHALL be allowed to connect to the support WebSocket for **only** their own conversation `public_id` and receive/send live events defined by the realtime messaging capability. Connecting to another customer's conversation MUST be denied.

#### Scenario: Customer joins own conversation socket

- **WHEN** an authenticated customer opens a WebSocket to their conversation public id with a valid token
- **THEN** the connection is accepted and they can receive `message.receive` events for that conversation

#### Scenario: Customer denied other conversation socket

- **WHEN** an authenticated customer attempts to connect to a different customer's conversation public id
- **THEN** the system MUST reject the connection without granting access to that history
