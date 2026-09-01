## MODIFIED Requirements

### Requirement: Customer can manage a labeled delivery place book
The system SHALL allow an authenticated customer to create, list, retrieve, update, and delete (or deactivate) their own delivery places. Each place MUST expose opaque `public_id` (UUID) as the client identity. Each place MUST include a human `label` and address fields sufficient for delivery (`full_address` required; `city`, `area`, `building_name`, `floor`, `flat_number`, `landmark`; coordinates required for geo-sourced saves as specified by delivery-place location enrichment). Delivery places MUST be independent of `present` / `permanent` identity addresses. The system MUST NOT allow a customer to access or mutate another customer’s places. Place resources MUST expose location metadata fields when present (`location_source` including `guest_migration` when applicable, `location_accuracy`, `formatted_address`, `is_verified_location`, `latitude`, `longitude`). Geo-updates MUST apply duplicate detection that excludes the place being updated.

#### Scenario: Create delivery place
- **WHEN** an authenticated customer creates a delivery place with a label and full address
- **THEN** the system responds `201` with the place including `public_id`, `label`, and address fields owned by that customer

#### Scenario: List own delivery places
- **WHEN** an authenticated customer requests their delivery places
- **THEN** the system responds `200` with only that customer’s places including location metadata fields

#### Scenario: Foreign place is not found
- **WHEN** an authenticated customer requests or mutates a delivery place `public_id` belonging to another customer
- **THEN** the system responds `404 Not Found`

#### Scenario: Unauthenticated access rejected
- **WHEN** an unauthenticated client calls delivery place endpoints
- **THEN** the system responds `401 Unauthorized`

### Requirement: Delivery place validation and soft limits
The system SHALL reject create/update payloads missing `full_address` or `label` with `422 Unprocessable Content`. The system SHALL enforce the maximum number of active delivery places per customer from admin-configurable `CustomerLocationSettings.max_active_delivery_places` (default 3) and reject creates beyond that limit with `422` and `error_code=ADDRESS_LIMIT_REACHED`.

#### Scenario: Missing full address rejected
- **WHEN** a customer submits a delivery place without `full_address`
- **THEN** the system responds `422` with a field error for `full_address`

#### Scenario: Soft cap enforced
- **WHEN** a customer already has the maximum allowed active delivery places and attempts to create another
- **THEN** the system responds `422` with `error_code=ADDRESS_LIMIT_REACHED` and does not create the place
