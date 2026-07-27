## Purpose

Verified-admin REST management of blog articles (title, content, cover image, category, publish lifecycle) with system-managed author and publish timestamps.

## Requirements

### Requirement: Admin blog article CRUD

The system SHALL expose a token-authenticated admin HTTP API for blog articles under `/blogs/articles/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete blog articles identified by `public_id`. Each article MUST support `title`, `content`, optional `excerpt`, optional `category_public_id`, `cover_image` (multipart), `cover_image_title`, and `is_published` (default `false`). Responses MUST include `public_id` and MUST NOT expose integer database primary keys as `id`. Anonymous users, customers, and unverified admins MUST be denied.

#### Scenario: Verified admin creates draft article
- **WHEN** a verified admin `POST`s a valid article payload to `/blogs/articles/`
- **THEN** the system returns `201 Created` with `is_published` false (unless explicitly published), `view_count` of `0`, and `public_id`

#### Scenario: Non-admin denied
- **WHEN** an anonymous or non-verified-admin user calls article admin endpoints
- **THEN** the system responds `401` or `403` as appropriate

#### Scenario: Invalid category rejected
- **WHEN** a verified admin submits an unknown `category_public_id`
- **THEN** the system rejects the request with a validation error

### Requirement: Author set from authenticated user

On article create, the system MUST set `author` from the authenticated verified admin user. Clients MUST NOT be able to assign or change the author via request body. Public and admin responses MUST expose a safe author display name and MUST NOT require clients to send author identifiers.

#### Scenario: Author assigned automatically
- **WHEN** verified admin A creates an article
- **THEN** the article’s author is A and the response includes an author display name derived from A

#### Scenario: Client author field ignored
- **WHEN** a create/update payload includes a client-supplied author identifier
- **THEN** the system does not reassign authorship based on that field

### Requirement: Publish timestamp and cover validation

When an article is first published (`is_published` becomes `true` while `published_at` is null), the system MUST set `published_at` to the current UTC time. Publishing MUST require a cover image; otherwise the system MUST reject with a validation error. Unpublishing MUST keep the existing `published_at` value.

#### Scenario: First publish sets published_at
- **WHEN** a draft article is patched to `is_published=true` and has a cover image
- **THEN** `published_at` is set to a non-null UTC timestamp

#### Scenario: Publish without cover rejected
- **WHEN** an admin attempts to publish an article that has no cover image
- **THEN** the system responds with a validation error and the article remains unpublished

#### Scenario: Unpublish keeps published_at
- **WHEN** a published article is set to `is_published=false`
- **THEN** `published_at` remains the original publish timestamp

### Requirement: Admin article list filters

The admin article list MUST support allowlisted filtering by `category_public_id` and `is_published`, plus search on `title`/`excerpt` where implemented, and MUST be paginated.

#### Scenario: Filter by published flag
- **WHEN** a verified admin lists articles with `is_published=true`
- **THEN** only published articles are returned

### Requirement: Admin article documentation

The change MUST ship frontend-facing documentation describing article admin endpoints, multipart cover upload, author behavior, publish workflow, and field meanings.

#### Scenario: Frontend admin article doc present
- **WHEN** the change is implemented
- **THEN** `blogs/docs/frontend/blog-admin.md` documents article CRUD with request/response examples
