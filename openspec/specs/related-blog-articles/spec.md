## Purpose

Unauthenticated related-article suggestions for a published blog article (same-category preference with global backfill).

## Requirements

### Requirement: Related articles endpoint

The system SHALL expose an unauthenticated HTTP endpoint `GET /blogs/public/{public_id}/related/` that returns suggested related published articles for the article identified by `public_id`. The endpoint MUST NOT require authentication. The source article itself MUST be excluded. Only `is_published=true` articles MUST be returned. The endpoint MUST accept a `limit` query parameter with a documented default and maximum (default 4, maximum 12).

#### Scenario: Related without auth
- **WHEN** an anonymous client `GET`s `/blogs/public/{public_id}/related/` for a published article
- **THEN** the system returns `200 OK` with a list of related published articles that does not include the source article

#### Scenario: Same category preferred
- **WHEN** the source article has a category and other published articles share that category
- **THEN** those same-category articles are preferred in the related results before unrelated backfill

#### Scenario: Backfill when category pool is small
- **WHEN** fewer than `limit` same-category published articles exist
- **THEN** the system backfills with other published articles (excluding the source and already selected items) until `limit` is reached or no more candidates exist

#### Scenario: No category uses global backfill
- **WHEN** the source article has no category
- **THEN** related results are chosen from other published articles using the backfill ordering rules

#### Scenario: Unknown or unpublished source
- **WHEN** the `public_id` does not identify a published article
- **THEN** the system responds `404 Not Found`

### Requirement: Related ordering and payload

Within each selection pool, related candidates MUST be ordered by `view_count` descending then `published_at` descending with a stable tie-breaker. Related items MUST use the public card payload shape (no full `content` required) and `public_id` identifiers.

#### Scenario: Related card shape
- **WHEN** related articles are returned
- **THEN** each item includes `public_id`, `title`, cover fields, `published_at`, and `view_count` suitable for a “Related articles” widget

### Requirement: Related articles documentation

The change MUST document the related endpoint path, `limit` behavior, matching rules (category preference + backfill), and example response for frontend integration.

#### Scenario: Related documented in public frontend doc
- **WHEN** the change is implemented
- **THEN** `blogs/docs/frontend/blog-public.md` documents `/blogs/public/{public_id}/related/` including matching rules
