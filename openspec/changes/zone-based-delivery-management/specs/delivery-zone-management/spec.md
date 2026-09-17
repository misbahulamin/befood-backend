## ADDED Requirements

### Requirement: Admin can create and list delivery zones
The system SHALL allow a verified admin to create operational delivery zones with `name`, unique `code`, `priority` (positive integer), and `status` (`active` or `inactive`). The system SHALL list zones paginated, ordered by `priority` ascending then `name`, exposing `public_id` (not integer PK) to API clients.

#### Scenario: Create zone
- **WHEN** a verified admin creates a zone with name, code, and priority
- **THEN** the system responds `201 Created` with the zone `public_id`, fields, and null assigned delivery man

#### Scenario: Duplicate code rejected
- **WHEN** a verified admin creates a zone whose `code` already exists
- **THEN** the system responds `422` (or project validation equivalent) and does not create a second zone

#### Scenario: List zones by priority
- **WHEN** a verified admin lists delivery zones
- **THEN** results are paginated and ordered by ascending priority

#### Scenario: Non-admin denied
- **WHEN** an unauthenticated or non-admin client attempts zone create or list
- **THEN** the system responds `401` or `403` as appropriate

### Requirement: Admin can update zone fields and priority
The system SHALL allow a verified admin to update zone `name`, `code`, `priority`, and `status` by `public_id`. Priority changes MUST remain unique among active zones per the uniqueness rule enforced by the service.

#### Scenario: Update priority
- **WHEN** a verified admin updates an existing zone priority to an unused value
- **THEN** the system responds `200` with the updated priority

#### Scenario: Unknown zone
- **WHEN** a verified admin updates a zone `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

### Requirement: Admin can assign a primary Delivery Man to a zone
The system SHALL allow a verified admin to assign exactly one primary Delivery Man (`RiderProfile`) to a zone, or clear the assignment. A Delivery Man MUST NOT be the primary assignee of two different zones at the same time. Only approved/verified Delivery Men MAY be assigned.

#### Scenario: Assign delivery man
- **WHEN** a verified admin assigns an approved Delivery Man to a zone that has no assignee
- **THEN** the zone stores that Delivery Man as primary assignee and responses include the deliveryman `public_id` and display name

#### Scenario: Same rider on second zone rejected
- **WHEN** a verified admin assigns a Delivery Man who is already primary on another zone
- **THEN** the system rejects the assignment with a conflict/validation error and leaves both zones unchanged

#### Scenario: Clear assignment
- **WHEN** a verified admin clears the assigned Delivery Man on a zone
- **THEN** the zone has no primary Delivery Man and the previous rider is free to be assigned elsewhere

### Requirement: Admin can deactivate or delete empty zones
The system SHALL allow deactivating a zone (`status=inactive`). The system MUST reject hard delete (or equivalent destructive remove) when the zone still has locations or when customers remain assigned through those locations, unless the admin first reassigns or removes dependents per documented rules.

#### Scenario: Deactivate zone
- **WHEN** a verified admin sets a zone status to `inactive`
- **THEN** the zone remains readable for history but MUST NOT accept new location assignments while inactive (create/move into inactive zone rejected)

#### Scenario: Delete zone with locations blocked
- **WHEN** a verified admin attempts to delete a zone that still has locations
- **THEN** the system rejects the delete and the zone remains
