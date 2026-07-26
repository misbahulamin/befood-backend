## ADDED Requirements

### Requirement: Verified-admin announcement CRUD
The system SHALL expose a token-authenticated admin HTTP API for announcements using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete announcements identified by `public_id`. Writable fields MUST include title, description, type, severity, optional image, optional CTA fields, `is_published`, optional `publish_at` / `publish_until`, and `priority`. Responses MUST include `public_id` and MUST NOT require Django Admin for these operations.

#### Scenario: Create announcement
- **WHEN** a verified admin POSTs a valid announcement payload
- **THEN** the system returns `201 Created` with the stored announcement including `public_id`

#### Scenario: Unauthenticated admin create is rejected
- **WHEN** an unauthenticated client POSTs to the admin announcements collection
- **THEN** the system returns `401 Unauthorized`

#### Scenario: Non-admin authenticated user is forbidden
- **WHEN** an authenticated non-verified-admin user attempts admin announcement CRUD
- **THEN** the system returns `403 Forbidden`

#### Scenario: Publish and unpublish via PATCH
- **WHEN** a verified admin PATCHes `is_published` to true or false
- **THEN** the system updates the flag and returns `200 OK` with the updated announcement

#### Scenario: Schedule a future announcement
- **WHEN** a verified admin creates or updates an announcement with `is_published=true` and `publish_at` in the future
- **THEN** the announcement is stored and MUST NOT appear in the public active feed until `publish_at`

#### Scenario: Lookup by public_id
- **WHEN** a verified admin retrieves, patches, or deletes by `public_id`
- **THEN** the system addresses that announcement and MUST NOT require the integer primary key in the URL

#### Scenario: Delete announcement
- **WHEN** a verified admin deletes an announcement by `public_id`
- **THEN** the system returns a successful delete response and the announcement MUST no longer be listable or retrievable

### Requirement: Admin image upload
The admin API MUST allow uploading an optional banner image on create or update using multipart form data when an image file is provided.

#### Scenario: Create with banner image
- **WHEN** a verified admin creates an announcement with a valid image file in multipart form data
- **THEN** the response includes an image URL (or media path) for the stored banner

#### Scenario: Update replaces banner image
- **WHEN** a verified admin PATCHes an existing announcement with a new image file
- **THEN** the stored image is replaced and the response reflects the new image

### Requirement: Admin list filters and pagination
The admin list endpoint MUST support filtering by `is_published`, `type`, and `severity`, searching title/description, deterministic ordering, and pagination with a documented default and maximum page size.

#### Scenario: Filter unpublished drafts
- **WHEN** a verified admin lists announcements with `is_published=false`
- **THEN** only unpublished announcements are returned

#### Scenario: Pagination bounds
- **WHEN** a verified admin requests a page size above the configured maximum
- **THEN** the system caps the page size at the maximum

### Requirement: Admin lifecycle status
Admin announcement payloads MUST include a computed `lifecycle_status` of `draft`, `scheduled`, `active`, or `expired` based on `is_published` and the schedule window at request time (UTC).

#### Scenario: Draft status
- **WHEN** `is_published` is false
- **THEN** `lifecycle_status` is `draft`

#### Scenario: Scheduled status
- **WHEN** `is_published` is true and `publish_at` is in the future
- **THEN** `lifecycle_status` is `scheduled`

### Requirement: Admin API documentation
The change MUST document the admin endpoint grid, Token auth (`IsVerifiedAdmin`), multipart image upload, request/response examples, filters, and how admin publish relates to the public active feed.

#### Scenario: Frontend admin docs exist
- **WHEN** the feature is delivered
- **THEN** `announcements/docs/frontend/announcements-admin.md` (or equivalent) describes auth, endpoints, and examples for the management UI
