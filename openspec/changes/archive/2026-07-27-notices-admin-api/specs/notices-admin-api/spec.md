## ADDED Requirements

### Requirement: Verified admin can CRUD site notices via API

The system SHALL expose a token-authenticated admin HTTP API for site notices using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete notices identified by `public_id`. Each writable notice MUST support bilingual titles/bodies, `severity` (`info` | `warning` | `critical`), `is_published`, optional `publish_at` / `publish_until`, and `sort_order`. Responses MUST include `public_id` and MUST NOT require Django Admin for these operations.

#### Scenario: Create draft notice

- **WHEN** a verified admin `POST`s a notice with English and Bangla titles and `is_published=false`
- **THEN** the system returns `201 Created` with a `public_id` and the notice MUST NOT appear on the public active feed

#### Scenario: Publish via patch

- **WHEN** a verified admin `PATCH`es an existing notice setting `is_published=true` within an open schedule window
- **THEN** the notice becomes eligible for the public active feed

#### Scenario: Retrieve by public_id

- **WHEN** a verified admin `GET`s `/notices/{public_id}/`
- **THEN** the system returns `200 OK` with the notice admin payload including publish fields

#### Scenario: Delete notice

- **WHEN** a verified admin `DELETE`s `/notices/{public_id}/`
- **THEN** the system returns `204 No Content` and the notice is removed from admin list and public feed

#### Scenario: Non-admin denied

- **WHEN** an anonymous client or non-admin authenticated user calls admin create, list, update, or delete
- **THEN** the system denies access (`401` or `403` as applicable)

### Requirement: Admin list supports filters and pagination

The admin notice list MUST support filtering by `is_published` and `severity`, optional text search across titles/bodies, deterministic ordering, and pagination with a default page size and maximum page size.

#### Scenario: Filter published only

- **WHEN** a verified admin lists notices with `is_published=true`
- **THEN** the response includes only published notices

#### Scenario: Filter by severity

- **WHEN** a verified admin lists notices with `severity=warning`
- **THEN** the response includes only notices with severity `warning`

### Requirement: Admin writes enforce notice validation

Admin create and update MUST reject payloads that violate notice business rules: both titles empty, invalid severity, or `publish_until` not after `publish_at` when both are set.

#### Scenario: Reject empty dual titles

- **WHEN** a verified admin creates a notice with blank `title_en` and `title_bn`
- **THEN** the system returns a validation error and does not create the notice

#### Scenario: Reject invalid schedule window

- **WHEN** a verified admin submits `publish_until` less than or equal to `publish_at`
- **THEN** the system returns a validation error

### Requirement: Admin payload includes lifecycle status

Admin list and detail responses MUST include a read-only `lifecycle_status` of `draft`, `scheduled`, `active`, or `expired` computed from `is_published` and the schedule window at response time.

#### Scenario: Draft status

- **WHEN** a verified admin retrieves an unpublished notice
- **THEN** `lifecycle_status` is `draft`

#### Scenario: Expired status

- **WHEN** a verified admin retrieves a published notice whose `publish_until` is in the past
- **THEN** `lifecycle_status` is `expired`

### Requirement: Admin API documentation is provided

The change MUST document the admin endpoint grid, Token auth (`IsVerifiedAdmin`), request/response examples, filters, and how admin publish relates to the public active feed.

#### Scenario: Frontend admin doc exists

- **WHEN** the change is completed
- **THEN** frontend documentation describes the admin notice CRUD contract with auth and examples
