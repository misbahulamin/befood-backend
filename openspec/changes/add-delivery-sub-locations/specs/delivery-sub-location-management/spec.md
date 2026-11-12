# Spec Delta

## Purpose

Admin operational CRUD for named sub-locations nested under a delivery location, so one neighborhood can hold multiple ordered delivery stops without duplicating zones or locations.

## ADDED Requirements

### Requirement: Admin can create a sub-location under a location
The system SHALL allow a verified admin to create a delivery sub-location with `name`, parent `location_public_id`, `priority` (positive integer unique among active sub-locations in that location), and `status` (`active` or `inactive`). Sub-locations MUST expose `public_id` to API clients.

#### Scenario: Create sub-location in location
- **WHEN** a verified admin creates sub-location "Gate A" under active location Chawkbazar with priority 1
- **THEN** the system responds `201 Created` with the sub-location `public_id`, name, priority, status, and parent location (and derived zone) summary

#### Scenario: Create under inactive location rejected
- **WHEN** a verified admin creates a sub-location whose parent location is inactive
- **THEN** the system rejects the create

#### Scenario: Duplicate priority in same location rejected
- **WHEN** a verified admin creates a sub-location with a priority already used by another active sub-location in the same location
- **THEN** the system rejects the create

### Requirement: Admin can list and filter sub-locations
The system SHALL provide a paginated sub-location list filterable by `location_public_id`, `zone_public_id`, and `status`, ordered by zone priority, location priority, sub-location priority, then name.

#### Scenario: Filter by location
- **WHEN** a verified admin lists sub-locations with `location_public_id` for Chawkbazar
- **THEN** only sub-locations belonging to Chawkbazar are returned, ordered by sub-location priority ascending

### Requirement: Admin can update and move a sub-location
The system SHALL allow updating sub-location `name`, `priority`, `status`, and parent location. Changing parent location MUST immediately change derived location and zone for all customers assigned to that sub-location without per-customer writes.

#### Scenario: Move sub-location to another location
- **WHEN** a verified admin moves "Gate A" from Chawkbazar to DC Road and customers are assigned to Gate A
- **THEN** those customers derive DC Road’s location and zone via Gate A with no separate customer assignment updates

#### Scenario: Move to inactive location rejected
- **WHEN** a verified admin attempts to move a sub-location into an inactive location
- **THEN** the system rejects the move and the sub-location’s parent is unchanged

### Requirement: Admin can deactivate or delete sub-locations safely
The system SHALL allow deactivating a sub-location. Destructive delete MUST be blocked while customers are still assigned; admin MUST reassign or clear those customers first.

#### Scenario: Delete sub-location with customers blocked
- **WHEN** a verified admin attempts to delete a sub-location that still has assigned customers
- **THEN** the system rejects the delete

#### Scenario: Deactivate sub-location
- **WHEN** a verified admin sets a sub-location to `inactive`
- **THEN** the sub-location remains for admin history and customers on it MUST NOT appear on active deliveryman boards until reassigned or the sub-location is reactivated per board rules

### Requirement: Location delete respects assigned sub-location customers
The system SHALL block deleting a delivery location while any customer remains assigned to a sub-location under that location (directly or via cascade rules documented for empty checks).

#### Scenario: Delete location with sub-location customers blocked
- **WHEN** a verified admin attempts to delete a location that has a sub-location with assigned customers
- **THEN** the system rejects the delete
