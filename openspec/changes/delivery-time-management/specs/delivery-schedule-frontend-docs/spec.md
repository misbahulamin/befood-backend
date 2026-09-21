## ADDED Requirements

### Requirement: Admin frontend delivery times management docs
The backend SHALL provide frontend documentation describing how the admin web app manages delivery schedules: base paths, auth (`Token` + verified admin), list/create/edit/delete payloads, `public_id` usage, `type=time` field mapping to API `HH:MM:SS` (or documented format), active/inactive UX, and error handling. The documented admin UI label SHOULD be “Delivery Times” (or equivalent) under the System navigation group.

#### Scenario: Admin can follow docs to wire CRUD
- **WHEN** a frontend engineer follows `delivery_schedules/docs/frontend/delivery-time-management.md`
- **THEN** they can implement list, create, edit, activate/deactivate, and delete against the admin API without inspecting backend source

### Requirement: Customer frontend display docs
The frontend documentation MUST describe the public GET contract for active schedules, the primary integration point (package detail policies currently hardcoded in `detailStaticContent.ts`), optional homepage TrustStrip/ServiceHub updates, sorting expectations, empty-state behavior, and how to format times for display without hardcoding schedule names or times in client source.

#### Scenario: Customer UI loads schedules from API
- **WHEN** the customer site implements the documented public integration on package detail (and optionally home)
- **THEN** newly created active admin schedules appear in the UI after refetch without a client code change to add the type name

### Requirement: Snake_case API field names in client docs
Documentation and examples MUST use project snake_case field names (`start_time`, `end_time`, `is_active`, `sort_order`, `public_id`), not camelCase, unless explicitly noting a client-side mapping layer.

#### Scenario: Example payload uses snake_case
- **WHEN** a reader opens the frontend delivery-time-management doc examples
- **THEN** request/response samples use `start_time` / `end_time` rather than `startTime` / `endTime`
