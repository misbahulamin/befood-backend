## ADDED Requirements

### Requirement: Delivery Man is scoped to an assigned zone
The system SHALL associate a Delivery Man with at most one primary zone (via zone assignment). A verified Delivery Man MUST only retrieve delivery board data for customers whose derived zone matches their assigned zone.

#### Scenario: Board limited to assigned zone
- **WHEN** Delivery Man Rahim is assigned to Zone 1 and requests today’s lunch board
- **THEN** only scheduled lunch deliveries for customers derived in Zone 1 are returned

#### Scenario: No zone assigned yields empty board
- **WHEN** a verified Delivery Man has no assigned zone and requests the today board
- **THEN** the system returns an empty delivery list (or an explicit empty-state payload) and MUST NOT leak other zones’ deliveries

#### Scenario: Cannot read another zone by query param
- **WHEN** a Delivery Man assigned to Zone 1 requests the board with a different `zone_public_id` filter
- **THEN** the system ignores the foreign zone or rejects the parameter and still returns only Zone 1 data

### Requirement: Admin can view Delivery Man zone binding
The system SHALL expose the assigned zone on admin Delivery Man detail/list (summary fields) and allow assignment through zone update and/or deliveryman admin update consistently with uniqueness rules.

#### Scenario: Admin sees assigned zone on deliveryman detail
- **WHEN** a verified admin retrieves a Delivery Man who is primary on Zone 2
- **THEN** the response includes Zone 2 `public_id` and name
