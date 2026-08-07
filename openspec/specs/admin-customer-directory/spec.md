## Purpose

Verified-admin web APIs for listing, searching, filtering, and viewing customer profile overviews identified by stable `public_id`.

## Requirements

### Requirement: Admin can list customers with basic information

The system SHALL provide a verified-admin web API collection at `/api/v1/web/customers/` that returns a paginated list of customer profiles. Each list item MUST include at least: customer `public_id`, display name, email, phone, `profile_picture_url` (nullable), account active flag, email verification status, registration timestamp (`User.date_joined`), and current meal package summary when an active order exists (package name and order `public_id` or null). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`.

#### Scenario: Verified admin lists customers

- **WHEN** a verified admin requests `GET /api/v1/web/customers/`
- **THEN** the system responds `200` with a paginated list of customers including the basic information fields above

#### Scenario: Unauthenticated list denied

- **WHEN** an unauthenticated client requests the admin customer list
- **THEN** the system responds `401 Unauthorized`

#### Scenario: Non-admin authenticated user denied

- **WHEN** an authenticated customer without verified-admin permission requests the admin customer list
- **THEN** the system responds `403 Forbidden`

#### Scenario: Profile picture absent

- **WHEN** a customer has no profile picture stored
- **THEN** the list item MUST include `profile_picture_url` with value `null`

### Requirement: Admin customer search

The system SHALL allow verified admins to search the customer list by name, email, and phone via an allowlisted query parameter (for example `q`). Matching MUST be case-insensitive for name and email. Unsupported or malformed search parameters that fail validation MUST yield `400 Bad Request` and MUST NOT be silently ignored when validation is enabled.

#### Scenario: Search by email fragment

- **WHEN** a verified admin lists customers with `q` matching part of a customer email
- **THEN** only customers whose name, email, or phone match that query MUST be returned

#### Scenario: Search by phone

- **WHEN** a verified admin lists customers with `q` matching a stored phone number
- **THEN** the matching customer MUST appear in the results

### Requirement: Admin customer filters

The system SHALL support allowlisted filters on the customer list for: active vs inactive account (`User.is_active`), email verification status, whether the customer has an active order, package (meal category) association for active-order customers, and registration date range on `User.date_joined`. Invalid enum values or unknown filter keys MUST be rejected with `400 Bad Request` when validation is enabled. Collections MUST use deterministic ordering with a unique tie-breaker.

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

#### Scenario: Unsupported filter rejected

- **WHEN** a verified admin supplies an unknown filter field or invalid enum value
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin can view customer detail overview

The system SHALL provide `GET /api/v1/web/customers/{public_id}/` for verified admins returning overview data: basic identity (name, email, phone), addresses / profile fields available on `CustomerProfile` and related address models, registration date, account status, verification status, current package summary, current wallet balance when a wallet exists, and summary metrics including at least total orders, total meals delivered, total meal-offs (skipped deliveries), total wallet spent (completed payment debits) and/or documented spending fields, last order date, and last activity date when computable. Unknown `public_id` MUST return `404`.

#### Scenario: Detail by public_id

- **WHEN** a verified admin requests a customer by `public_id`
- **THEN** the system responds `200` with overview fields and summary metrics for that customer

#### Scenario: Unknown public_id

- **WHEN** a verified admin requests a customer `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

#### Scenario: Verification status maps to email verification

- **WHEN** a verified admin retrieves a customer whose `is_email_verified` is true
- **THEN** the detail payload MUST present verification as verified (and MUST NOT require a separate customer `is_verified` field)

### Requirement: Customer public identifiers for admin APIs

The system SHALL identify customers in admin web customer APIs by a stable UUID `public_id` on `CustomerProfile`. Path parameters and list/detail payloads MUST expose `public_id` and MUST NOT require clients to use sequential database primary keys for these endpoints.

#### Scenario: List and detail use public_id

- **WHEN** a verified admin lists customers and opens one detail URL
- **THEN** the detail path uses the same `public_id` returned in the list item
