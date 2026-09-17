## ADDED Requirements

### Requirement: Admin can view zone-wise delivery counts
The system SHALL provide a verified-admin ops summary for a required `service_date` and `meal_period` that returns per-zone scheduled (and optionally delivered/skipped) delivery counts for customers derived in each zone.

#### Scenario: Zone counts for lunch
- **WHEN** a verified admin requests ops summary for a date with `meal_period=lunch`
- **THEN** the response lists each active zone with lunch delivery counts for that date

### Requirement: Admin can view location-wise delivery counts
The system SHALL include per-location counts within each zone (or as a flat list keyed by location) in the same ops summary or a documented sibling endpoint.

#### Scenario: Location counts inside zone
- **WHEN** a verified admin requests ops summary and Zone 1 has Chawkbazar and DC Road deliveries
- **THEN** the response includes separate counts for Chawkbazar and DC Road

### Requirement: Admin can view Delivery Man workload
The system SHALL expose workload per assigned Delivery Man for the requested date and meal period (at least scheduled count; preferably delivered and skipped counts) based on their primary zone membership.

#### Scenario: Workload for assigned rider
- **WHEN** Zone 1 is assigned to Delivery Man Rahim and has 25 scheduled lunch deliveries
- **THEN** ops summary shows Rahim’s workload scheduled count as 25 for that lunch slot

#### Scenario: Zone without rider still counted
- **WHEN** a zone has scheduled deliveries but no assigned Delivery Man
- **THEN** zone and location counts still appear and the deliveryman workload section marks the zone as unassigned
