## ADDED Requirements

### Requirement: Admin customer list and detail expose operational location and derived zone
The system SHALL include on admin customer list/detail (when loaded) the customer’s assigned delivery location summary and derived zone summary (`public_id`, name, priority) when a location is set, or nulls when unassigned.

#### Scenario: Detail shows location and zone
- **WHEN** a verified admin retrieves a customer assigned to Chawkbazar in Zone 1
- **THEN** the response includes Chawkbazar location fields and derived Zone 1 fields

#### Scenario: Unassigned customer shows null location
- **WHEN** a verified admin retrieves a customer with no delivery location
- **THEN** location and zone fields are null/omitted per documented serializer contract

### Requirement: Admin can assign customer delivery location from customer APIs
The system SHALL allow a verified admin to set or clear `delivery_location_public_id` on the customer via the admin customer update (or dedicated nested assign) endpoint, subject to location active-status validation.

#### Scenario: Assign via admin customer update
- **WHEN** a verified admin PATCHes a customer with a valid active `delivery_location_public_id`
- **THEN** the customer is assigned that location and subsequent reads show the derived zone
