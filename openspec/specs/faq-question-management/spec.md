## Purpose

Verified-admin REST management of FAQ questions and answers under FAQ types, including publish/unpublish visibility for the public FAQ page.

## Requirements

### Requirement: Verified admin FAQ question CRUD

The system SHALL expose a token-authenticated admin HTTP API for FAQ questions under `/faqs/questions/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete FAQ questions identified by `public_id`. Each question MUST belong to exactly one existing FAQ type via `type_public_id`, MUST have non-blank `question` and `answer` text, MUST have `is_published` (default `false`), and MUST have `sort_order` (default `0`). Responses MUST include `public_id` and `type_public_id`. Anonymous users, customers, and unverified admins MUST be denied.

#### Scenario: Verified admin creates a published question
- **WHEN** a verified admin `POST`s `/faqs/questions/` with `type_public_id`, `question`, `answer`, and `is_published=true`
- **THEN** the system creates the question under that type and returns `201 Created`

#### Scenario: New question defaults to unpublished
- **WHEN** a verified admin `POST`s `/faqs/questions/` without `is_published`
- **THEN** the system stores the question with `is_published=false`

#### Scenario: Verified admin publishes via PATCH
- **WHEN** a verified admin `PATCH`es `/faqs/questions/{public_id}/` with `is_published=true`
- **THEN** the system updates the flag and returns `200 OK`

#### Scenario: Verified admin unpublishes via PATCH
- **WHEN** a verified admin `PATCH`es `/faqs/questions/{public_id}/` with `is_published=false`
- **THEN** the system updates the flag and returns `200 OK`

#### Scenario: Verified admin lists questions including drafts
- **WHEN** a verified admin `GET`s `/faqs/questions/`
- **THEN** the system returns both published and unpublished questions

#### Scenario: Filter questions by type
- **WHEN** a verified admin `GET`s `/faqs/questions/?type_public_id={uuid}`
- **THEN** the system returns only questions belonging to that type

#### Scenario: Filter questions by publish flag
- **WHEN** a verified admin `GET`s `/faqs/questions/?is_published=true`
- **THEN** the system returns only published questions

#### Scenario: Question requires an existing type
- **WHEN** a verified admin `POST`s `/faqs/questions/` with a missing or unknown `type_public_id`
- **THEN** the system rejects the request with a validation error

#### Scenario: Verified admin deletes a question
- **WHEN** a verified admin `DELETE`s `/faqs/questions/{public_id}/`
- **THEN** the system deletes the question and returns `204 No Content`

#### Scenario: Non-admin denied
- **WHEN** an anonymous user or non-admin authenticated user calls `/faqs/questions/`
- **THEN** the system denies the request (`401` or `403` as appropriate)

### Requirement: FAQ question public identifiers

Admin FAQ question retrieve, update, and delete endpoints MUST look up questions by `public_id`. Client responses MUST expose `public_id` (and `type_public_id` for the parent type) and MUST NOT expose integer primary keys as API `id` fields.

#### Scenario: Lookup by public_id
- **WHEN** a verified admin `GET`s `/faqs/questions/{public_id}/` with a valid UUID
- **THEN** the system returns that question including `type_public_id`
