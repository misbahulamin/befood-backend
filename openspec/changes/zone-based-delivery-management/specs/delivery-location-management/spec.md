## ADDED Requirements

### Requirement: Admin can create locations inside a zone
The system SHALL allow a verified admin to create a delivery location with `name`, parent `zone_public_id`, `priority` (positive integer unique among active locations in that zone), and `status` (`active` or `inactive`). Locations MUST expose `public_id` to API clients.

#### Scenario: Create location in zone
- **WHEN** a verified admin creates location "Chawkbazar" in an active zone with priority 1
- **THEN** the system responds `201 Created` with the location `public_id`, name, priority, and parent zone summary

#### Scenario: Create location in inactive zone rejected
- **WHEN** a verified admin creates a location whose parent zone is inactive
- **THEN** the system rejects the create

#### Scenario: Duplicate priority in same zone rejected
- **WHEN** a verified admin creates a location with a priority already used by another active location in the same zone
- **THEN** the system rejects the create

### Requirement: Admin can update location and change its zone
The system SHALL allow updating location `name`, `priority`, `status`, and parent zone. Changing parent zone MUST immediately change the derived zone for all customers assigned to that location without requiring per-customer updates.

#### Scenario: Move location to another zone
- **WHEN** a verified admin moves location "Chawkbazar" from Zone 1 to Zone 2 and 100 customers are assigned to Chawkbazar
- **THEN** all 100 customers derive Zone 2 membership via Chawkbazar and no separate customer zone write is required

#### Scenario: Move to inactive zone rejected
- **WHEN** a verified admin attempts to move a location into an inactive zone
- **THEN** the system rejects the move and the location’s zone is unchanged

### Requirement: Admin can list and filter locations
The system SHALL provide paginated location list filtered by `zone_public_id` and `status`, ordered by zone priority then location priority then name.

#### Scenario: Filter by zone
- **WHEN** a verified admin lists locations with `zone_public_id` for Zone 1
- **THEN** only locations belonging to Zone 1 are returned, ordered by location priority ascending

### Requirement: Admin can deactivate or delete locations safely
The system SHALL allow deactivating a location. Destructive delete MUST be blocked while customers are still assigned to the location; admin MUST reassign or clear customer locations first.

#### Scenario: Delete location with customers blocked
- **WHEN** a verified admin attempts to delete a location that still has assigned customers
- **THEN** the system rejects the delete

#### Scenario: Deactivate location
- **WHEN** a verified admin sets a location to `inactive`
- **THEN** the location remains for admin history and customers assigned to it MUST NOT appear on active deliveryman boards for that location until reassigned or location reactivated per board rules
