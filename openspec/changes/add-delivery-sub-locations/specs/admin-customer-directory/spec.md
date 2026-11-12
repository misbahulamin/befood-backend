# Spec Delta

## ADDED Requirements

### Requirement: Admin customer list and detail expose operational sub-location and derived location and zone
The system SHALL include on admin customer list/detail the customer’s assigned delivery sub-location summary and derived location and zone summaries (`public_id`, name, priority as applicable) when a sub-location is set, or nulls when unassigned.

#### Scenario: Detail shows sub-location location and zone
- **WHEN** a verified admin retrieves a customer assigned to Gate A under Chawkbazar in Zone 1
- **THEN** the response includes Gate A sub-location fields, derived Chawkbazar location fields, and derived Zone 1 fields

#### Scenario: Unassigned customer shows null hierarchy
- **WHEN** a verified admin retrieves a customer with no delivery sub-location
- **THEN** sub-location, location, and zone fields are null/omitted per documented serializer contract

## MODIFIED Requirements

### Requirement: Admin customer filters

The system SHALL support allowlisted filters on the customer list for: active vs inactive account (`User.is_active`), email verification status, whether the customer has an active order, package (meal category) association for active-order customers, registration date range on `User.date_joined`, and operational delivery hierarchy filters `zone_public_id`, `location_public_id`, `sub_location_public_id`, and `has_delivery_sub_location`. Invalid enum values or unknown filter keys MUST be rejected with `400 Bad Request` when validation is enabled. Collections MUST use deterministic ordering with a unique tie-breaker.

#### Scenario: Filter active customers

- **WHEN** a verified admin lists customers with `is_active=true`
- **THEN** only customers whose linked user is active MUST be returned

#### Scenario: Filter inactive customers

- **WHEN** a verified admin lists customers with `is_active=false`
- **THEN** only customers whose linked user is inactive MUST be returned

#### Scenario: Filter customers with active order

- **WHEN** a verified admin lists customers with `has_active_order=true`
- **THEN** only customers who have at least one order with `order_status=active` MUST be returned

#### Scenario: Filter customers with no active order

- **WHEN** a verified admin lists customers with `has_active_order=false`
- **THEN** customers without an active order MUST be returned and customers with an active order MUST be excluded

#### Scenario: Filter by package

- **WHEN** a verified admin lists customers with a package public id filter
- **THEN** only customers whose active order references that meal package MUST be returned

#### Scenario: Filter by registration date range

- **WHEN** a verified admin lists customers with `registered_from` and/or `registered_to`
- **THEN** only customers whose `date_joined` falls within the documented inclusive range MUST be returned

#### Scenario: Filter by sub-location

- **WHEN** a verified admin lists customers with `sub_location_public_id` for Gate A
- **THEN** only customers assigned to Gate A MUST be returned

#### Scenario: Filter customers without sub-location

- **WHEN** a verified admin lists customers with `has_delivery_sub_location=false`
- **THEN** only customers with no delivery sub-location MUST be returned

#### Scenario: Unsupported filter rejected

- **WHEN** a verified admin supplies an unknown filter field or invalid enum value
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin can view customer detail overview

The system SHALL provide `GET /api/v1/web/customers/{public_id}/` for verified admins returning overview data: basic identity (name, email, phone), addresses / profile fields available on `CustomerProfile` and related address models, registration date, account status, verification status, current package summary, current wallet balance when a wallet exists, operational delivery sub-location and derived location/zone summaries when assigned, and summary metrics including at least total orders, total meals delivered, total meal-offs (skipped deliveries), total wallet spent (completed payment debits) and/or documented spending fields, last order date, and last activity date when computable. Unknown `public_id` MUST return `404`.

#### Scenario: Detail by public_id

- **WHEN** a verified admin requests a customer by `public_id`
- **THEN** the system responds `200` with overview fields and summary metrics for that customer

#### Scenario: Unknown public_id

- **WHEN** a verified admin requests a customer `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

#### Scenario: Verification status maps to email verification

- **WHEN** a verified admin retrieves a customer whose `is_email_verified` is true
- **THEN** the detail payload MUST present verification as verified (and MUST NOT require a separate customer `is_verified` field)

#### Scenario: Detail includes delivery hierarchy when assigned

- **WHEN** a verified admin retrieves a customer assigned to an active sub-location
- **THEN** the overview includes non-null sub-location and derived location and zone summaries
