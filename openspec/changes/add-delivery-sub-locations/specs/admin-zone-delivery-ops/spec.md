# Spec Delta

## Purpose

Verified-admin ops summary for zone delivery planning that counts today’s deliveries by zone, location, and sub-location, plus unassigned customers.

## ADDED Requirements

### Requirement: Admin can view zone-wise delivery counts
The system SHALL provide a verified-admin ops summary for a required `service_date` and `meal_period` that returns per-zone scheduled (and optionally delivered/skipped) delivery counts for customers derived in each zone.

#### Scenario: Zone counts for lunch
- **WHEN** a verified admin requests ops summary for a date with `meal_period=lunch`
- **THEN** the response lists each active zone with lunch delivery counts for that date

### Requirement: Admin can view location-wise and sub-location-wise delivery counts
The system SHALL include per-location and per-sub-location counts within each zone in the same ops summary or a documented sibling field set.

#### Scenario: Sub-location counts inside location
- **WHEN** a verified admin requests ops summary and Zone 1 / Chawkbazar has Gate A and Gate B deliveries
- **THEN** the response includes separate counts for Gate A and Gate B under Chawkbazar

### Requirement: Admin can view Delivery Man workload
The system SHALL expose workload per assigned Delivery Man for the requested date and meal period (at least scheduled count; preferably delivered and skipped counts) based on their primary zone membership.

#### Scenario: Workload for assigned rider
- **WHEN** Zone 1 is assigned to Delivery Man Rahim and has 25 scheduled lunch deliveries
- **THEN** ops summary shows Rahim’s workload scheduled count as 25 for that lunch slot

### Requirement: Ops summary includes unassigned sub-location count
The system SHALL include a count of scheduled deliveries whose customers have no delivery sub-location for the requested service date and meal period.

#### Scenario: Unassigned count present
- **WHEN** three scheduled lunch deliveries belong to customers without a sub-location
- **THEN** ops summary reports unassigned count of at least 3 for that lunch slot
