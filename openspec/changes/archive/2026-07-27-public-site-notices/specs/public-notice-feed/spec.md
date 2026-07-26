## ADDED Requirements

### Requirement: Public active notice feed requires no authentication

The system SHALL expose a public HTTP API to list currently active site notices. Unauthenticated clients MUST be allowed to call this endpoint. The response MUST include only notices that satisfy the active rule (`is_published` and within the schedule window at request time).

#### Scenario: Anonymous visitor lists active notices

- **WHEN** an unauthenticated client sends `GET /notices/active/`
- **THEN** the system returns `200 OK` with the list of currently active notices

#### Scenario: Draft notices are hidden

- **WHEN** only unpublished notices exist
- **THEN** `GET /notices/active/` returns an empty list (or empty page results) and does not leak draft content

#### Scenario: Expired notices are hidden

- **WHEN** a published notice’s `publish_until` is in the past
- **THEN** that notice is omitted from `GET /notices/active/`

### Requirement: Active feed payload is bilingual and lean

Each active notice in the public response MUST include `public_id`, `title_en`, `title_bn`, `body_en`, `body_bn`, `severity`, `publish_at`, `publish_until`, and `sort_order`. The payload MUST NOT include internal admin-only fields beyond this public contract.

#### Scenario: Response includes both locales

- **WHEN** an active notice has both English and Bangla title and body filled
- **THEN** the public response includes all four text fields so the frontend can select by locale

#### Scenario: Severity is returned for UI styling

- **WHEN** an active notice has `severity=warning`
- **THEN** the public response includes `"severity": "warning"`

### Requirement: Active notices are ordered deterministically

The public active list MUST order notices by `sort_order` ascending, then by newest schedule/create time as a deterministic tie-breaker, and MUST apply pagination with a default page size and a maximum page size.

#### Scenario: Lower sort_order appears first

- **WHEN** two active notices exist with `sort_order` 1 and 10
- **THEN** the notice with `sort_order` 1 appears before the notice with `sort_order` 10

#### Scenario: Pagination bounds enforced

- **WHEN** a client requests a `page_size` above the configured maximum
- **THEN** the system caps the page size at the maximum (or rejects with `400` per project pagination conventions)

### Requirement: Public feed documentation is provided

The change MUST ship frontend-facing documentation describing the public endpoint path, lack of authentication, response JSON examples, locale selection guidance, and empty/active UI states.

#### Scenario: Frontend doc exists for site notices

- **WHEN** the change is completed
- **THEN** `notices/docs/frontend/site-notices.md` documents the public contract with success examples
