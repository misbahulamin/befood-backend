## ADDED Requirements

### Requirement: Public list of active delivery schedules
The system SHALL expose an unauthenticated GET endpoint that returns only delivery schedules with `is_active=true`, ordered by ascending `sort_order`, then `name`, then stable id. Inactive schedules MUST NOT appear. The response MUST use `public_id` as the client identity and MUST include `name`, `start_time`, `end_time`, and `sort_order` (snake_case JSON per project convention).

#### Scenario: Active schedules returned in display order
- **WHEN** the database contains active Lunch (sort_order 1), active Dinner (sort_order 2), and inactive Breakfast
- **THEN** a public GET returns Lunch then Dinner and omits Breakfast

#### Scenario: Empty catalog
- **WHEN** no active schedules exist
- **THEN** the public GET returns `200` with an empty list

#### Scenario: No authentication required
- **WHEN** an anonymous client calls the public delivery-schedules list
- **THEN** the system returns `200` without requiring login

### Requirement: Public catalog stays small and read-only
The public delivery-schedules endpoint MUST be read-only (GET/HEAD/OPTIONS only). Clients MUST NOT create, update, or delete schedules through the public endpoint.

#### Scenario: Public write rejected
- **WHEN** an anonymous or authenticated non-admin client POSTs, PATCHes, or DELETEs on the public delivery-schedules path
- **THEN** the system rejects the method (e.g. `405`) or the route does not expose those methods
