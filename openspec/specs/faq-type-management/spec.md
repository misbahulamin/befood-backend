## Purpose

Verified-admin REST management of FAQ types (sections/categories) that group questions on the public FAQ page.

## Requirements

### Requirement: Verified admin FAQ type CRUD

The system SHALL expose a token-authenticated admin HTTP API for FAQ types under `/faqs/types/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete FAQ types identified by `public_id`. Each type MUST have a non-blank `name`, a `sort_order` integer (default `0`), and an `is_active` boolean (default `true`). Responses MUST include `public_id` and MUST NOT expose operations to anonymous users or non-admin authenticated users. Unverified admins MUST be denied.

#### Scenario: Verified admin creates a type
- **WHEN** a verified admin `POST`s `/faqs/types/` with a unique `name` and optional `sort_order`
- **THEN** the system creates the type with a new `public_id` and returns `201 Created`

#### Scenario: Verified admin lists types
- **WHEN** a verified admin `GET`s `/faqs/types/`
- **THEN** the system returns types ordered by `sort_order` ascending then a stable tie-breaker, including inactive types

#### Scenario: Verified admin updates a type
- **WHEN** a verified admin `PATCH`es `/faqs/types/{public_id}/` with a new `name` or `sort_order` or `is_active`
- **THEN** the system updates the type and returns `200 OK`

#### Scenario: Verified admin deletes an empty type
- **WHEN** a verified admin `DELETE`s `/faqs/types/{public_id}/` that has no questions
- **THEN** the system deletes the type and returns `204 No Content`

#### Scenario: Delete type blocked when questions exist
- **WHEN** a verified admin `DELETE`s `/faqs/types/{public_id}/` that still has one or more questions
- **THEN** the system rejects the request with `409 Conflict` or `422 Unprocessable Content` and does not delete the type

#### Scenario: Duplicate type name rejected
- **WHEN** a verified admin `POST`s `/faqs/types/` with a `name` that already exists
- **THEN** the system rejects the request with a validation error

#### Scenario: Unverified or non-admin denied
- **WHEN** an anonymous user, a customer, or an unverified admin calls any `/faqs/types/` write or list endpoint
- **THEN** the system denies the request (`401` or `403` as appropriate)

### Requirement: FAQ type public identifiers

Admin FAQ type retrieve, update, and delete endpoints MUST look up types by `public_id`. Client responses MUST expose `public_id` and MUST NOT expose the integer primary key as `id`.

#### Scenario: Lookup by public_id
- **WHEN** a verified admin `GET`s `/faqs/types/{public_id}/` with a valid UUID
- **THEN** the system returns that type

#### Scenario: Integer path is not a public identifier
- **WHEN** a client requests a type using a sequential integer path as if it were the public identifier
- **THEN** the system MUST NOT resolve the type successfully
