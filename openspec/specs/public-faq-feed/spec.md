## Purpose

Unauthenticated public nested FAQ catalog for the website FAQ page — active types with published questions only.

## Requirements

### Requirement: Public nested FAQ catalog

The system SHALL expose an unauthenticated HTTP endpoint `GET /faqs/public/` that returns FAQ types together with nested questions for the public website FAQ page. The endpoint MUST NOT require authentication credentials. The response MUST include only active types (`is_active=true`) and, within each type, only questions where `is_published` is `true`. Unpublished questions MUST NEVER appear in this response.

#### Scenario: Public catalog without auth
- **WHEN** an anonymous client `GET`s `/faqs/public/`
- **THEN** the system returns `200 OK` with a JSON list of types, each containing a nested `questions` array of published entries only

#### Scenario: Unpublished questions excluded
- **WHEN** a type has both published and unpublished questions
- **THEN** the public catalog response for that type includes only the published questions

#### Scenario: Empty types omitted
- **WHEN** an active type has zero published questions
- **THEN** that type MUST NOT appear in the public catalog response

#### Scenario: Inactive types excluded
- **WHEN** a type has `is_active=false` even if it has published questions
- **THEN** that type MUST NOT appear in the public catalog response

#### Scenario: Deterministic ordering
- **WHEN** the public catalog is returned
- **THEN** types are ordered by `sort_order` ascending (stable tie-breaker) and nested questions are ordered by `sort_order` ascending (stable tie-breaker)

#### Scenario: No unpublished leakage in payload
- **WHEN** the public catalog is returned
- **THEN** nested question objects MUST NOT include an `is_published` field set to false, and MUST NOT list unpublished question text

### Requirement: Public FAQ response contract

Each type object in the public catalog MUST include at least `public_id`, `name`, `sort_order`, and `questions`. Each nested question MUST include at least `public_id`, `question`, `answer`, and `sort_order`. The public API MUST NOT expose integer database primary keys as `id`.

#### Scenario: Public shape includes identifiers and copy
- **WHEN** a client receives a non-empty public catalog
- **THEN** each type and question entry includes `public_id` and the display fields needed to render the FAQ page

### Requirement: Public FAQ documentation

The change MUST ship frontend-facing documentation describing the public endpoint path, lack of authentication, nested JSON examples, ordering, empty-state behavior (no types / only unpublished), and guidance that the FAQ page should render types as sections and questions as items under each section.

#### Scenario: Frontend public doc present
- **WHEN** the change is implemented
- **THEN** `faqs/docs/frontend/faq-public.md` documents the public contract with request/response examples
