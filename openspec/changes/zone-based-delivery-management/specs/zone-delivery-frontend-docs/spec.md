## ADDED Requirements

### Requirement: Frontend docs for zone and location admin UI
The system SHALL provide frontend-facing documentation describing admin flows to create/update/deactivate zones and locations, set priorities, assign a Delivery Man to a zone, move a location between zones, and understand cascade effects on customers.

#### Scenario: Docs cover cascade behavior
- **WHEN** a frontend engineer reads the zone-delivery frontend docs
- **THEN** the docs explain that moving a location between zones updates all assigned customers’ derived zone without a bulk customer API call

### Requirement: Frontend docs for customer location assignment
The system SHALL document how admin customer detail/list shows location and derived zone, and which field (`delivery_location_public_id`) to PATCH when assigning.

#### Scenario: Docs include assign field contract
- **WHEN** a frontend engineer implements customer location assignment
- **THEN** the docs specify request field names, success response shape, and validation errors for inactive/missing locations

### Requirement: Frontend docs for deliveryman board and admin ops
The system SHALL document the deliveryman today-board response shape (lunch/dinner, priority grouping, address fields) and the admin ops summary query parameters and count fields.

#### Scenario: Docs include board example payload
- **WHEN** a frontend engineer builds the Delivery Man dashboard
- **THEN** the docs include an example JSON payload with totals and priority-grouped customers
