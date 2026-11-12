# Spec Delta

## Purpose

Frontend developer documentation for Admin Panel delivery-zones hierarchy and related customer assignment / board contracts after sub-locations are introduced.

## ADDED Requirements

### Requirement: Document Zone → Location → Sub-location admin UI contract
The system SHALL maintain frontend documentation at `delivery_zones/docs/frontend/zone-based-delivery.md` that describes Admin Panel page `admin/delivery-zones`: create/list/update/deactivate zones, locations under zones, and sub-locations under locations, including auth headers, endpoint grid, request/response examples, and empty/error states.

#### Scenario: Docs cover sub-location CRUD
- **WHEN** a frontend engineer opens the zone-based delivery frontend doc
- **THEN** the doc shows how to create a sub-location under a location, list by `location_public_id`, update/move, and delete-or-deactivate safely

### Requirement: Document customer assignment to sub-location
The frontend documentation MUST explain assigning customers via `delivery_sub_location_public_id`, derived location/zone display fields, compatibility behavior for legacy `delivery_location_public_id` during the documented window, and list filters for zone/location/sub-location.

#### Scenario: Docs show assign payload
- **WHEN** a frontend engineer implements customer assignment from the admin UI
- **THEN** the doc includes a PATCH example using `delivery_sub_location_public_id` and clear/null semantics

### Requirement: Document board and ops payload additions
The frontend documentation MUST describe deliveryman board nesting (location → sub-location → customers) and ops summary sub-location counts so Admin Panel and Delivery Man clients can render the new hierarchy without guessing field names.

#### Scenario: Docs show board nesting fields
- **WHEN** a frontend engineer updates the today board UI
- **THEN** the doc lists the sub-location identifier and name fields returned inside each location group

### Requirement: Document phased rollout for Admin Panel
The frontend documentation MUST state the recommended deploy order (backend expand + backfill → frontend dual-aware → backend contract tighten) so the Admin Panel at `/admin/delivery-zones` does not break while AWS production still serves mixed clients.

#### Scenario: Docs state dual-aware UI guidance
- **WHEN** a frontend engineer reads the rollout section
- **THEN** the doc states that UI MUST prefer sub-location assignment APIs while temporarily tolerating responses that still echo derived location during the compatibility window
