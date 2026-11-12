# Spec Delta

## Purpose

Zone-scoped Delivery Man today board that lists meal deliveries ordered and grouped by location then sub-location priorities for efficient neighborhood routing.

## ADDED Requirements

### Requirement: Delivery Man board groups by location then sub-location
The system SHALL provide a verified Delivery Man today board scoped to their assigned zone. The response MUST include delivery totals for the active meal period and customers grouped (or nested) by location priority then sub-location priority, each entry exposing location name, sub-location name, and address fields already used by the board.

#### Scenario: Nested location and sub-location groups
- **WHEN** a Delivery Man assigned to Zone 1 requests the today board and Zone 1 has Chawkbazar/Gate A and Chawkbazar/Gate B scheduled deliveries
- **THEN** the response includes both groups under Chawkbazar ordered by sub-location priority, each with address and sub-location name

#### Scenario: Only assigned zone deliveries
- **WHEN** the Delivery Man requests the board
- **THEN** only deliveries for customers whose derived zone is the rider’s assigned zone are returned

### Requirement: Board ordering uses location priority then sub-location priority
The system SHALL order board entries by location `priority` ascending, then sub-location `priority` ascending, then a deterministic tie-break (for example customer name or delivery `public_id`).

#### Scenario: Priority order across locations
- **WHEN** Priority 1 location Chawkbazar and Priority 2 location DC Road both have scheduled deliveries
- **THEN** Chawkbazar deliveries appear before DC Road deliveries

#### Scenario: Priority order within location
- **WHEN** Chawkbazar has Gate A priority 1 and Gate B priority 2 with scheduled deliveries
- **THEN** Gate A deliveries appear before Gate B deliveries

### Requirement: Inactive or missing sub-location excludes from active board
The system SHALL omit deliveries whose customer has no active delivery sub-location (or whose sub-location or parent location is inactive per documented board rules) from the default active board listing.

#### Scenario: Customer without sub-location omitted
- **WHEN** a customer in the rider’s zone has no delivery sub-location and has a scheduled delivery
- **THEN** that delivery MUST NOT appear on the deliveryman today board

### Requirement: Unauthenticated or non-deliveryman access denied
The system SHALL reject board access for unauthenticated clients and for authenticated users who are not verified Delivery Men.

#### Scenario: Customer cannot open deliveryman board
- **WHEN** an authenticated customer requests the deliveryman today board
- **THEN** the system responds `403 Forbidden`
