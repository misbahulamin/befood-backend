## ADDED Requirements

### Requirement: Most popular articles endpoint

The system SHALL expose an unauthenticated HTTP endpoint `GET /blogs/public/popular/` that returns the published articles with the highest `view_count` for the public website “Most Popular” UI. The endpoint MUST NOT require authentication. Only `is_published=true` articles MUST be included. Results MUST be ordered by `view_count` descending, then `published_at` descending, with a stable tie-breaker. The endpoint MUST accept a `limit` query parameter with a documented default and maximum (default 5, maximum 20); values above the maximum MUST be clamped or rejected consistently (prefer clamp).

#### Scenario: Popular list without auth
- **WHEN** an anonymous client `GET`s `/blogs/public/popular/`
- **THEN** the system returns `200 OK` with a list of published articles ordered by highest `view_count` first

#### Scenario: Drafts excluded from popular
- **WHEN** an unpublished article has a high view_count
- **THEN** it MUST NOT appear in the popular response

#### Scenario: Limit controls result size
- **WHEN** a client requests `/blogs/public/popular/?limit=3`
- **THEN** the system returns at most 3 articles

#### Scenario: Popular payload is card-shaped
- **WHEN** the popular list is returned
- **THEN** each item includes card fields suitable for a sidebar/widget (including `public_id`, `title`, cover image, `view_count`, `published_at`) and MUST NOT require loading full `content`

### Requirement: Popular articles documentation

The change MUST document the popular endpoint path, `limit` behavior, ordering rules, and example response for frontend integration.

#### Scenario: Popular documented in public frontend doc
- **WHEN** the change is implemented
- **THEN** `blogs/docs/frontend/blog-public.md` documents `/blogs/public/popular/` including limit and ordering
