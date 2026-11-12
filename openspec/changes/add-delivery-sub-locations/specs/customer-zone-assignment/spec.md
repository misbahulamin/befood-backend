# Spec Delta

## Purpose

Admin assignment of customers to operational delivery sub-locations, with location and zone always derived from the sub-location hierarchy for routing and boards.

## ADDED Requirements

### Requirement: Admin can assign a customer to a delivery sub-location
The system SHALL allow a verified admin to set or clear a customer’s operational `delivery_sub_location` by sub-location `public_id`. The customer’s location and zone MUST be derived from that sub-location’s parent location and zone and MUST be exposed on admin customer representations as read-only summaries when a sub-location is set.

#### Scenario: Assign sub-location
- **WHEN** a verified admin assigns customer Rahim to sub-location Gate A under Chawkbazar in Zone 1
- **THEN** Rahim’s profile stores Gate A and admin customer detail shows derived Chawkbazar and Zone 1

#### Scenario: Change sub-location
- **WHEN** a verified admin changes Rahim from Gate A to Gate B (same or different location)
- **THEN** Rahim’s derived location and zone become Gate B’s parent location and zone immediately

#### Scenario: Clear sub-location
- **WHEN** a verified admin clears a customer’s delivery sub-location
- **THEN** the customer has no derived location or zone and MUST NOT appear on any zone-scoped deliveryman board

#### Scenario: Assign inactive sub-location rejected
- **WHEN** a verified admin assigns a customer to an inactive sub-location
- **THEN** the system rejects the assignment

### Requirement: Location and zone membership cascade from hierarchy moves
The system SHALL treat customer location and zone membership as derived only. After a sub-location’s parent location changes, or that location’s zone changes, every customer assigned to the sub-location MUST resolve to the new location and zone without additional customer writes.

#### Scenario: Cascade after location zone move
- **WHEN** Chawkbazar moves from Zone 1 to Zone 2 and Rahim is assigned to Gate A under Chawkbazar
- **THEN** reading Rahim’s admin detail shows Zone 2 derived via Gate A → Chawkbazar

### Requirement: Unassigned customers are visible to admin ops
The system SHALL allow admins to identify customers (or today’s deliveries for customers) who have no operational delivery sub-location, so they can be assigned before dispatch.

#### Scenario: Unassigned count on ops summary
- **WHEN** a verified admin requests zone delivery ops summary for a service date and meal period
- **THEN** the response includes a count of scheduled deliveries whose customers have no delivery sub-location

### Requirement: Compatibility window for legacy location assignment
During the documented compatibility window, the system SHALL accept legacy admin assignment by `delivery_location_public_id` by resolving that location’s designated default (or sole) sub-location when present. After the window ends, location-only assignment MUST be rejected and clients MUST send `delivery_sub_location_public_id`.

#### Scenario: Legacy location assign maps to default sub-location
- **WHEN** compatibility is enabled and a verified admin assigns a customer with only `delivery_location_public_id` for a location that has a default sub-location
- **THEN** the customer is stored against that default sub-location and subsequent reads expose the sub-location

#### Scenario: Post-compat location-only assign rejected
- **WHEN** compatibility is disabled and a verified admin sends only `delivery_location_public_id` without a sub-location
- **THEN** the system rejects the assignment with a validation error directing clients to use sub-location assignment
