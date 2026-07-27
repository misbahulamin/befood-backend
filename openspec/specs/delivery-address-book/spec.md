## Purpose

Authenticated customers manage a labeled delivery place book (Home, Office, …) independent of present/permanent identity addresses, with ownership isolation and safe delete rules when places are referenced by meal preferences.

## Requirements

### Requirement: Customer can manage a labeled delivery place book
The system SHALL allow an authenticated customer to create, list, retrieve, update, and delete (or deactivate) their own delivery places. Each place MUST expose opaque `public_id` (UUID) as the client identity. Each place MUST include a human `label` and address fields sufficient for delivery (`full_address` required; `city`, `area`, `building_name`, `floor`, `flat_number`, `landmark`, optional coordinates). Delivery places MUST be independent of `present` / `permanent` identity addresses. The system MUST NOT allow a customer to access or mutate another customer’s places.

#### Scenario: Create delivery place
- **WHEN** an authenticated customer creates a delivery place with a label and full address
- **THEN** the system responds `201` with the place including `public_id`, `label`, and address fields owned by that customer

#### Scenario: List own delivery places
- **WHEN** an authenticated customer requests their delivery places
- **THEN** the system responds `200` with only that customer’s places

#### Scenario: Foreign place is not found
- **WHEN** an authenticated customer requests or mutates a delivery place `public_id` belonging to another customer
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated access rejected
- **WHEN** an unauthenticated client calls delivery place endpoints
- **THEN** the system responds `401 Unauthorized`

### Requirement: Delivery place validation and soft limits
The system SHALL reject create/update payloads missing `full_address` or `label` with `422 Unprocessable Content`. The system SHALL enforce a documented maximum number of active delivery places per customer and reject creates beyond that limit with `422`.

#### Scenario: Missing full address rejected
- **WHEN** a customer submits a delivery place without `full_address`
- **THEN** the system responds `422` with a field error for `full_address`

#### Scenario: Soft cap enforced
- **WHEN** a customer already has the maximum allowed active delivery places and attempts to create another
- **THEN** the system responds `422` and does not create the place

### Requirement: Deleting or deactivating a place used by preferences is safe
The system SHALL prevent hard-deletion of a delivery place that is currently referenced by the customer’s lunch default, dinner default, or an active day override, unless the client first reassigns or clears those references. Historical `OrderDelivery` snapshots MUST remain intact when a place is removed (`delivery_place` FK may become null while snapshot text remains).

#### Scenario: Delete blocked while place is lunch default
- **WHEN** a customer attempts to delete a place that is set as their lunch preference
- **THEN** the system responds `409 Conflict` (or `422`) explaining the place is in use and does not delete it

#### Scenario: Snapshot survives place removal after preferences cleared
- **WHEN** a place is no longer referenced by preferences and is deleted after past deliveries used it
- **THEN** those `OrderDelivery` rows retain their address snapshot fields even if the place FK is cleared
