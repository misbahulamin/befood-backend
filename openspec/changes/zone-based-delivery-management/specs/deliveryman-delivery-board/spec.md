## ADDED Requirements

### Requirement: Delivery Man can view today’s lunch and dinner boards
The system SHALL provide a verified Delivery Man API to retrieve today’s (or requested `service_date`) deliveries for `lunch` and/or `dinner`, scoped to their assigned zone. The response MUST include total delivery count for the period and a customer list with customer display name, delivery address (from order-delivery snapshot and/or resolved place), location name, and location priority.

#### Scenario: Lunch board with priority groups
- **WHEN** a Delivery Man assigned to a zone requests the lunch board for a service date that has deliveries in locations with priorities 1 and 2
- **THEN** the response includes total lunch count and customers grouped or ordered by location priority ascending, each with address and location name

#### Scenario: Dinner board independent of lunch
- **WHEN** the same Delivery Man requests the dinner board for the same date
- **THEN** only dinner-period deliveries for the assigned zone are returned with the same grouping fields

#### Scenario: Default excludes terminal statuses unless requested
- **WHEN** a Delivery Man requests the board without a status filter
- **THEN** the default set MUST include `scheduled` deliveries and MAY include `delivered` only when explicitly requested via documented filter

### Requirement: Board ordering uses location priority then stable tie-break
The system SHALL order board entries by location `priority` ascending, then by a deterministic tie-break (for example customer name or delivery `public_id`).

#### Scenario: Priority 1 before priority 2
- **WHEN** a zone has Priority 1 location Chawkbazar and Priority 2 location DC Road with scheduled deliveries
- **THEN** Chawkbazar deliveries appear before DC Road deliveries in the board ordering

### Requirement: Unauthenticated or non-deliveryman access denied
The system SHALL reject board access for unauthenticated clients and for authenticated users who are not verified Delivery Men.

#### Scenario: Customer cannot open deliveryman board
- **WHEN** an authenticated customer requests the deliveryman today board
- **THEN** the system responds `403 Forbidden`
