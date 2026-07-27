## ADDED Requirements

### Requirement: Public published article list

The system SHALL expose an unauthenticated HTTP endpoint `GET /blogs/public/` that returns a paginated list of published blog articles for the public website. The endpoint MUST NOT require authentication. Only articles with `is_published=true` MUST appear. List items MUST omit full `content` (card fields only). The public API MUST NOT expose integer database primary keys as `id`.

#### Scenario: Public list without auth
- **WHEN** an anonymous client `GET`s `/blogs/public/`
- **THEN** the system returns `200 OK` with a paginated list of published articles

#### Scenario: Drafts excluded from list
- **WHEN** unpublished articles exist
- **THEN** they MUST NOT appear in `/blogs/public/`

#### Scenario: List omits full content
- **WHEN** the public list is returned
- **THEN** each item includes card fields such as `public_id`, `title`, `excerpt`, cover image URL, `cover_image_title`, author display name, `published_at`, and `view_count`, and MUST NOT include the full article `content` body

#### Scenario: Deterministic ordering
- **WHEN** the public list is returned without an alternate sort
- **THEN** articles are ordered by `published_at` descending with a stable tie-breaker

### Requirement: Public article detail and view increment

The system SHALL expose `GET /blogs/public/{public_id}/` that returns a single published article including `content`. On successful retrieval, the system MUST atomically increment that article’s `view_count` by one. Unpublished or unknown articles MUST return `404`. List, popular, related, and admin endpoints MUST NOT increment view counts.

#### Scenario: Detail returns content and increments views
- **WHEN** an anonymous client `GET`s a published article detail
- **THEN** the system returns `200 OK` with `content` and the article’s `view_count` increases by one

#### Scenario: Unpublished detail not found
- **WHEN** a client requests detail for an unpublished article public_id
- **THEN** the system responds `404 Not Found` and does not increment any view count

#### Scenario: Missing article not found
- **WHEN** a client requests detail for an unknown public_id
- **THEN** the system responds `404 Not Found`

### Requirement: Public blog response contract

Public article objects MUST use `public_id` as the client identifier. Nested category (when present) MUST use `public_id` and `name`. Author MUST be represented as a display name suitable for the website (not a privileged user id). Timestamps MUST be UTC RFC 3339 style values consistent with project conventions.

#### Scenario: Public shape uses public_id
- **WHEN** a client receives a public list or detail payload
- **THEN** article (and category, if nested) identifiers are `public_id` values and integer PK `id` is absent

### Requirement: Public blog documentation

The change MUST ship frontend-facing documentation describing public list and detail paths, lack of authentication, pagination, the view-count side effect on detail, empty states, and response examples.

#### Scenario: Frontend public doc present
- **WHEN** the change is implemented
- **THEN** `blogs/docs/frontend/blog-public.md` documents the public list/detail contract with examples
