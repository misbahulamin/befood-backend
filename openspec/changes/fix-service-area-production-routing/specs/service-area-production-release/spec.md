## ADDED Requirements

### Requirement: Production URL conf mounts service-area routes
The deployed backend SHALL include the public service-area routes under `/api/v1/service-areas/` and the web admin routes under `/api/v1/web/service-areas/` in the root URL configuration, and SHALL list `service_area` in `INSTALLED_APPS`.

#### Scenario: Admin list path is registered
- **WHEN** a client sends `GET /api/v1/web/service-areas/` to the production host after release
- **THEN** Django MUST NOT return a URL-resolver “Page not found” for an unmatched path
- **AND** the response MUST be produced by the service-area admin view (authenticated success, or auth/permission error JSON — not an HTML unmatched-route page)

#### Scenario: Public check path is registered
- **WHEN** a client sends `POST /api/v1/service-areas/check/` with a JSON body containing latitude and longitude after release
- **THEN** Django MUST NOT return a URL-resolver “Page not found” for an unmatched path
- **AND** the response MUST be a JSON success or validation/domain error from the check view

### Requirement: Production database has service-area schema
The production release process MUST apply `service_area` migrations so that service hub and request history tables exist before traffic is accepted as healthy.

#### Scenario: Migration applied
- **WHEN** the release migrate step completes successfully
- **THEN** the `service_area` initial migration MUST be recorded as applied
- **AND** creating a hub via the admin API MUST persist without a missing-relation database error

### Requirement: Post-deploy smoke verification
Operators MUST be able to verify release health with a short smoke checklist covering route presence and a happy-path check against an active hub (when hubs exist).

#### Scenario: Smoke checklist passes
- **WHEN** an operator runs the post-deploy smoke checks after migrate
- **THEN** admin list and public check endpoints MUST resolve
- **AND** at least one automated or documented manual check MUST confirm the endpoint is not a URL 404
