## ADDED Requirements

### Requirement: Admin can assign a customer to a delivery location
The system SHALL allow a verified admin to set or clear a customer’s operational `delivery_location` by location `public_id`. The customer’s zone MUST be derived from that location’s current zone and MUST be exposed on admin customer representations as read-only zone fields (`zone_public_id`, zone name, zone priority) when a location is set.

#### Scenario: Assign location
- **WHEN** a verified admin assigns customer Rahim to location Chawkbazar which belongs to Zone 1
- **THEN** Rahim’s profile stores Chawkbazar and admin customer detail shows derived Zone 1

#### Scenario: Change location
- **WHEN** a verified admin changes Rahim from Chawkbazar to DC Road (same or different zone)
- **THEN** Rahim’s derived zone becomes DC Road’s zone immediately

#### Scenario: Clear location
- **WHEN** a verified admin clears a customer’s delivery location
- **THEN** the customer has no derived zone and MUST NOT appear on any zone-scoped deliveryman board

#### Scenario: Assign inactive location rejected
- **WHEN** a verified admin assigns a customer to an inactive location
- **THEN** the system rejects the assignment

### Requirement: Location zone move cascades to customers
The system SHALL treat customer zone membership as derived only. After a location’s parent zone changes, every customer assigned to that location MUST resolve to the new zone without additional customer writes.

#### Scenario: Cascade after location move
- **WHEN** Chawkbazar moves from Zone 1 to Zone 2 and Rahim is assigned to Chawkbazar
- **THEN** reading Rahim’s admin detail shows Zone 2 derived from Chawkbazar

### Requirement: Unassigned customers are visible to admin ops
The system SHALL allow admins to identify customers (or today’s deliveries for customers) who have no operational delivery location, so they can be assigned before dispatch.

#### Scenario: Unassigned count on ops summary
- **WHEN** a verified admin requests zone delivery ops summary for a service date and meal period
- **THEN** the response includes a count of scheduled deliveries whose customers have no delivery location
