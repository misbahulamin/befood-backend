## ADDED Requirements

### Requirement: Admin Delivery Man representations expose assigned zone
The system SHALL include the primary assigned delivery zone (`public_id`, name, priority) on admin Delivery Man list and detail responses when the rider is assigned to a zone, or null when unassigned.

#### Scenario: Detail includes zone
- **WHEN** a verified admin retrieves a Delivery Man who is primary on Zone 1
- **THEN** the response includes Zone 1 summary fields

### Requirement: Admin can assign or clear Delivery Man zone binding
The system SHALL allow a verified admin to assign a Delivery Man to an active zone or clear the binding, enforcing that a Delivery Man is primary on at most one zone and that only approved/verified Delivery Men can be assigned.

#### Scenario: Assign zone from deliveryman admin API
- **WHEN** a verified admin assigns an approved Delivery Man to an active zone that has no primary rider
- **THEN** the binding is stored and both deliveryman detail and zone detail reflect the assignment

#### Scenario: Conflict when rider already assigned
- **WHEN** a verified admin assigns a Delivery Man who is already primary on another zone without clearing the previous binding
- **THEN** the system rejects the change with a conflict/validation error
