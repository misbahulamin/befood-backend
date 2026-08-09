## ADDED Requirements

### Requirement: Admin-managed service hubs with radius coverage
The system SHALL persist service hubs (`ServiceArea`) with a unique public identifier, human-readable name, latitude, longitude, radius in kilometers (`radius_km`), active flag (`is_active`), optional description, optional created-by admin reference, and created/updated timestamps. Coverage for customers MUST be defined solely by the hub coordinates and `radius_km`, not by equality between the hub name and any customer area name.

#### Scenario: Create an active hub
- **WHEN** a verified admin creates a hub named `Chawkbazar Hub` with latitude/longitude and `radius_km` of `5`
- **THEN** the system stores the hub as active (unless explicitly created inactive) and exposes its `public_id`, name, coordinates, radius, and status

#### Scenario: Hub name is not used for customer matching
- **WHEN** a customer location display name is `GEC Circle` and an active hub is named `Chawkbazar Hub`
- **THEN** the system MUST NOT treat name inequality alone as non-serviceable; matching uses geographic distance only

### Requirement: Validate hub geographic fields
The system MUST reject hub create/update requests with missing latitude or longitude, latitude outside `[-90, 90]`, longitude outside `[-180, 180]`, or non-positive `radius_km`. Radius MUST be stored with decimal precision suitable for kilometer distances (at least two decimal places).

#### Scenario: Reject invalid coordinates
- **WHEN** a verified admin submits latitude `120` for a hub
- **THEN** the system returns a validation error and does not persist the hub

#### Scenario: Reject non-positive radius
- **WHEN** a verified admin submits `radius_km` of `0` or a negative value
- **THEN** the system returns a validation error and does not persist the hub

### Requirement: Activate and deactivate hubs
The system SHALL allow verified admins to activate or deactivate a hub. Inactive hubs MUST be excluded from customer serviceability matching. Historical request rows MAY retain a foreign key to a hub that later becomes inactive.

#### Scenario: Deactivated hub excluded from matching
- **WHEN** a hub is `is_active=false` and a customer check falls inside that hub’s former radius
- **THEN** the verification service MUST NOT treat that hub as a covering match

#### Scenario: Reactivate hub
- **WHEN** a verified admin sets a hub back to `is_active=true`
- **THEN** subsequent customer checks MAY match that hub again using its current radius and coordinates

### Requirement: Soft delete or hard delete policy for hubs
The system SHALL support deleting a hub through the admin API. If requests reference the hub, the system MUST either soft-delete (hide from matching and admin default lists) or nullify/retain historical FKs without cascading wipe of analytics history. Public APIs MUST NOT expose deleted hubs as active coverage.

#### Scenario: Delete does not erase request history
- **WHEN** an admin deletes a hub that has prior `ServiceAreaRequest` rows
- **THEN** those historical request rows remain queryable for analytics (with hub reference cleared or soft-deleted marker as implemented) and are not hard-wiped solely by hub deletion
