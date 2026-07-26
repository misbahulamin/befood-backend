## ADDED Requirements

### Requirement: Public active announcement feed
The system SHALL expose an unauthenticated HTTP list endpoint that returns only currently active announcements for the public website. The endpoint MUST NOT require authentication credentials and MUST NOT return draft, unpublished, scheduled-future, or expired announcements.

#### Scenario: List active announcements without auth
- **WHEN** an anonymous client calls `GET /announcements/active/`
- **THEN** the system returns `200 OK` with a paginated list of active announcements

#### Scenario: Empty active set
- **WHEN** no announcements satisfy the active rule
- **THEN** the system returns `200 OK` with an empty results list

#### Scenario: Draft excluded
- **WHEN** an announcement has `is_published=false`
- **THEN** it MUST NOT appear in the active feed

#### Scenario: Future schedule excluded
- **WHEN** an announcement is published but `publish_at` is after the current time
- **THEN** it MUST NOT appear in the active feed

#### Scenario: Inclusive expiry boundary
- **WHEN** an announcement is published and `publish_until` equals the current evaluation time
- **THEN** it MUST still appear in the active feed

#### Scenario: Past expiry excluded
- **WHEN** an announcement is published and `publish_until` is before the current time
- **THEN** it MUST NOT appear in the active feed

### Requirement: Active feed ordering
The active feed MUST order results by `priority` descending, then newest first (`created_at` descending), with a deterministic tie-breaker.

#### Scenario: Priority then newest
- **WHEN** multiple announcements are active
- **THEN** higher `priority` appears before lower `priority`, and equal priorities prefer the newer `created_at`

### Requirement: Lean public payload
Public active announcement objects MUST expose fields needed for popup rendering: `public_id`, `title`, `description`, `type`, `severity`, `image` (URL or null), `button_text`, `button_url`, `publish_at`, `publish_until`, and `priority`. The public payload MUST NOT expose internal management-only fields beyond what is required for display (for example it MUST NOT require clients to interpret draft flags that are already filtered out).

#### Scenario: CTA and image available to website
- **WHEN** an active announcement has an image and CTA fields
- **THEN** the public response includes those values so the website can render an image popup and redirect on CTA click

#### Scenario: Text-only announcement
- **WHEN** an active announcement has no image and empty CTA fields
- **THEN** the public response still includes title/description/type/severity for a text-only notice popup

### Requirement: Public feed pagination
The active feed MUST be paginated with a documented default page size and a hard maximum page size.

#### Scenario: Default page size
- **WHEN** a client omits `page_size`
- **THEN** the system applies the documented default page size

### Requirement: Public integration documentation
The change MUST document the public endpoint, no-auth usage, response examples, field meanings, priority display guidance, and client-side dismiss behavior (e.g. store dismissed `public_id` values in `localStorage` so the same popup is not shown repeatedly in a session).

#### Scenario: Frontend public docs exist
- **WHEN** the feature is delivered
- **THEN** `announcements/docs/frontend/announcements-public.md` (or equivalent) describes the website integration flow including dismiss/localStorage guidance
