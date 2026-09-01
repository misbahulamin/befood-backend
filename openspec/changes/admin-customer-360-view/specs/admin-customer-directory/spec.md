## MODIFIED Requirements

### Requirement: Admin can list customers with basic information

The system SHALL provide a verified-admin web API collection at `/api/v1/web/customers/` that returns a paginated list of customer profiles. Each list item MUST include at least: customer `public_id`, display name, email, phone, `profile_picture_url` (nullable), account active flag, email verification status, registration timestamp (`User.date_joined`), and current meal package summary when an **active subscription** exists (package name and subscription `public_id` or null). When no active subscription exists but a legacy active order exists, the list item MAY fall back to the legacy order summary for `current_package` until legacy orders are fully retired. Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`.

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

#### Scenario: Subscribed customer shows current package

- **WHEN** a customer has an active `CustomerSubscription`
- **THEN** the list item `current_package` MUST reflect that subscription's plan name and subscription `public_id`

### Requirement: Admin customer filters

The system SHALL support allowlisted filters on the customer list for: active vs inactive account (`User.is_active`), email verification status, whether the customer has an **active subscription** (`has_active_subscription`), whether the customer has a legacy active order (`has_active_order`, deprecated alias), whether the customer has a wallet (`has_wallet`), whether the customer has a pending manual recharge request (`has_pending_recharge`), whether the customer's active subscription is expiring within a documented window (`subscription_expiring_soon`), whether the customer has subscription history but no active subscription (`inactive_subscription`), package (meal category) association for active-subscription customers, and registration date range on `User.date_joined`. Invalid enum values or unknown filter keys MUST be rejected with `400 Bad Request` when validation is enabled. Collections MUST use deterministic ordering with a unique tie-breaker.

#### Scenario: Filter active customers

- **WHEN** a verified admin lists customers with `is_active=true`
- **THEN** only customers whose linked user is active MUST be returned

#### Scenario: Filter inactive customers

- **WHEN** a verified admin lists customers with `is_active=false`
- **THEN** only customers whose linked user is inactive MUST be returned

#### Scenario: Filter customers with active subscription

- **WHEN** a verified admin lists customers with `has_active_subscription=true`
- **THEN** only customers who have a `CustomerSubscription` with `status=active` MUST be returned

#### Scenario: Filter customers with no active subscription

- **WHEN** a verified admin lists customers with `has_active_subscription=false`
- **THEN** customers without an active subscription MUST be returned and customers with an active subscription MUST be excluded

#### Scenario: Filter by package

- **WHEN** a verified admin lists customers with a package public id filter
- **THEN** only customers whose active subscription (or legacy active order when no subscription) references that meal package MUST be returned

#### Scenario: Filter by registration date range

- **WHEN** a verified admin lists customers with `registered_from` and/or `registered_to`
- **THEN** only customers whose `date_joined` falls within the documented inclusive range MUST be returned

#### Scenario: Unsupported filter rejected

- **WHEN** a verified admin supplies an unknown filter field or invalid enum value
- **THEN** the system responds `400 Bad Request`

#### Scenario: Filter customers with pending recharge

- **WHEN** a verified admin lists customers with `has_pending_recharge=true`
- **THEN** only customers who have at least one pending manual wallet recharge request MUST be returned

#### Scenario: Filter customers with wallet

- **WHEN** a verified admin lists customers with `has_wallet=true`
- **THEN** only customers who have a wallet row MUST be returned

### Requirement: Admin can view customer detail overview

The system SHALL provide `GET /api/v1/web/customers/{public_id}/` for verified admins returning a **lean overview** containing: profile (basic identity, addresses, profile fields), registration date, account status, verification status, nullable **active subscription summary**, nullable **wallet summary**, and aggregate `summary` metrics. The overview MUST NOT embed paginated history arrays (subscriptions list, meal rows, wallet transaction rows, or activity events). History MUST remain on dedicated paginated sub-resources. Summary metrics MUST include at least: total subscriptions, total legacy orders (when applicable), total meals delivered (subscription + legacy order deliveries), total meal-offs, customer lifetime value (documented field, defaulting to total completed wallet spend), total wallet recharged, total wallet withdrawn, `last_payment_at`, `last_meal_delivered_at`, `current_package_expires_at` (nullable), `last_subscription_at`, `last_legacy_order_at`, `last_activity_at`, and wallet balance/currency when a wallet exists. Unknown `public_id` MUST return `404`.

#### Scenario: Detail by public_id

- **WHEN** a verified admin requests a customer by `public_id`
- **THEN** the system responds `200` with overview fields and summary metrics for that customer

#### Scenario: Unknown public_id

- **WHEN** a verified admin requests a customer `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

#### Scenario: Verification status maps to email verification

- **WHEN** a verified admin retrieves a customer whose `is_email_verified` is true
- **THEN** the detail payload MUST present verification as verified (and MUST NOT require a separate customer `is_verified` field)

#### Scenario: Subscribed customer detail includes active subscription

- **WHEN** a verified admin retrieves a customer with an active subscription and no legacy active order
- **THEN** the detail payload MUST include a non-null `active_subscription` summary and MUST NOT require a legacy active order to represent the current service

#### Scenario: Overview excludes history arrays

- **WHEN** a verified admin requests customer detail for a customer with many subscriptions, meals, and wallet transactions
- **THEN** the overview response MUST NOT include paginated history arrays and MUST only include profile, summary, active subscription summary, and wallet summary

#### Scenario: Customer cannot read another customer's detail

- **WHEN** an authenticated customer user (Customer A) requests `GET /api/v1/web/customers/{customer-B-public-id}/`
- **THEN** the system responds `403 Forbidden` and MUST NOT return Customer B's data

## ADDED Requirements

### Requirement: Admin detail exposes active subscription summary

The system SHALL include an `active_subscription` object (nullable) on the customer detail overview and a dedicated sub-resource `GET /api/v1/web/customers/{public_id}/active-subscription/` returning `{ "active_subscription": ... }`. When present, the payload MUST include at least: subscription `public_id`, package/plan name, subscription `status` (value from backend model/serializer choices, not a hardcoded frontend enum), start date, end date (nullable for open-ended), remaining scheduled meal count, delivered meal count, skipped meal count, and payment/billing status fields documented for admin read models.

#### Scenario: Customer with active subscription

- **WHEN** a verified admin requests active subscription for a customer with `CustomerSubscription.status=active`
- **THEN** the response includes package name, status, start date, remaining meals, and documented payment status fields

#### Scenario: Customer without active subscription

- **WHEN** a verified admin requests active subscription for a customer with no active subscription
- **THEN** the system responds `200` with `active_subscription: null` and MUST NOT return another customer's subscription
