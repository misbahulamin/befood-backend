# Spec Delta

## MODIFIED Requirements

### Requirement: Admin can list support conversations

The system SHALL provide a verified-admin web API at `GET /api/v1/web/support/conversations/` that returns a paginated list of customer support conversations. Each list item MUST include at least: conversation `public_id`, customer display name, phone, email (nullable if absent), last message preview, last message time, `last_message_sender` (`customer`, `admin`, or null when no messages), admin unread count, and conversation status (`open`, `closed`, or `archived`). The list contract MUST allow clients to display online status when presence data is available (field may be computed/ephemeral, not necessarily a DB column). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`. Ordering MUST be by most recent `last_message_at` descending with NULL timestamps last, then by descending unique id tie-breaker. By default the list MUST exclude conversations with no messages (`last_message_at` null) unless `include_empty=true` is supplied.

#### Scenario: Verified admin lists conversations

- **WHEN** a verified admin requests `GET /api/v1/web/support/conversations/`
- **THEN** the system responds `200` with a paginated list including the required customer, last-message, and `last_message_sender` fields

#### Scenario: Non-admin denied

- **WHEN** an authenticated customer without verified-admin permission requests the admin conversation list
- **THEN** the system responds `403 Forbidden`

#### Scenario: Newest message sorts before older and empty threads

- **WHEN** conversations exist with recent messages, older messages, and null `last_message_at`
- **THEN** the list order MUST place the newest non-null `last_message_at` first and MUST NOT place any null `last_message_at` conversation before a conversation that has messages

#### Scenario: Default list excludes empty conversations

- **WHEN** a verified admin lists conversations without `include_empty=true`
- **THEN** conversations with null `last_message_at` MUST NOT appear in the result set

#### Scenario: last_message_sender after customer then admin

- **WHEN** a customer posts a message and later an admin replies
- **THEN** the list item for that conversation MUST report `last_message_sender` as `customer` after the customer message and as `admin` after the admin reply

### Requirement: Admin conversation filters and search

The system SHALL support allowlisted filters for conversation `status`, admin unread (e.g. `has_unread=true`), and `include_empty` (boolean; default false), and MUST support search `q` against customer name, phone, or email. Search and filtered lists MUST also exclude empty conversations unless `include_empty=true`. Unknown filter keys MUST be rejected with `400` when validation is enabled.

#### Scenario: Filter by open status

- **WHEN** a verified admin lists conversations with `status=open`
- **THEN** only conversations with status `open` MUST be returned

#### Scenario: Filter unread conversations

- **WHEN** a verified admin lists conversations with an unread filter enabled
- **THEN** only conversations with admin unread count greater than zero MUST be returned

#### Scenario: Search by phone

- **WHEN** a verified admin lists conversations with `q` matching a customer phone
- **THEN** conversations for matching customers MUST be included in the result set when they are otherwise eligible (including the empty-conversation default)

#### Scenario: include_empty returns empty threads at end

- **WHEN** a verified admin lists with `include_empty=true` and both empty and non-empty conversations exist
- **THEN** empty conversations MAY be included and MUST sort after all conversations that have messages

#### Scenario: Unsupported filter rejected

- **WHEN** a verified admin lists with an unknown query parameter
- **THEN** the system responds `400` indicating unsupported filters

## ADDED Requirements

### Requirement: Admin list documents include_empty and last_message_sender

Admin conversation list OpenAPI and frontend docs MUST document `include_empty`, default empty exclusion, NULLS LAST ordering, and the `last_message_sender` response field.

#### Scenario: Contract docs mention new list fields

- **WHEN** an integrator reads the admin support inbox API documentation after this change
- **THEN** `include_empty` and `last_message_sender` MUST be described with allowed values and default behavior
