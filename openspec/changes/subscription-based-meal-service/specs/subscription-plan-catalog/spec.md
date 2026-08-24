## ADDED Requirements

### Requirement: Subscription plans are MealCategory packages flagged as subscribable

The system SHALL treat `MealCategory` as the subscription plan catalog. A package is a subscription plan when `is_subscribable` is true. Plan identity for clients MUST be the meal `public_id`. Each plan MUST store at least: `meal_name`, `description`, `meal_thumbnail`, `meal_period` (`lunch` | `dinner` | `both`), `is_active`, `is_subscribable`, and published `total_price` when priced. `meal_type` MUST NOT bound how long a customer remains subscribed.

#### Scenario: Admin creates a new Premium-style plan

- **WHEN** a verified admin creates a subscription plan with name `Premium`, `meal_period=both`, `is_active=true`, and `is_subscribable=true`
- **THEN** the system persists a `MealCategory` with that configuration and returns its `public_id`

#### Scenario: Duration packages are not in the subscribe catalog by default

- **WHEN** a `MealCategory` has `is_subscribable=false`
- **THEN** it MUST NOT appear in the customer subscription-plan catalog even if `is_active=true`

### Requirement: Verified admin can create and manage subscription plans

The system SHALL expose a token-authenticated verified-admin API to list, create, retrieve, and partially update subscription plans identified by `public_id`. Create and update MUST accept the plan configuration fields needed to add a future package without a code deploy. Non-admin and unauthenticated clients MUST be denied (`401` or `403`). Unverified admins MUST be denied. Clients MUST NOT be required to use integer primary keys.

#### Scenario: Admin lists plans

- **WHEN** a verified admin lists subscription plans
- **THEN** the system responds `200` with a paginated list including `public_id`, name, meal period, active and subscribable flags, and pricing display fields

#### Scenario: Admin deactivates a plan

- **WHEN** a verified admin patches `is_active=false` on an existing plan
- **THEN** subsequent customer catalog reads omit that plan, and existing active subscriptions for that plan MUST remain active until the customer cancels

#### Scenario: Customer cannot create a plan

- **WHEN** a verified customer POSTs to the admin subscription-plans collection
- **THEN** the system responds `401` or `403` and creates no plan

### Requirement: Customer can list available subscription plans

The system SHALL provide an authenticated verified-customer catalog of plans where `is_active=true` and `is_subscribable=true`. The payload MUST be lean (identity, name, description, thumbnail, meal period, price when published). Inactive or non-subscribable packages MUST be omitted. Unauthenticated requests MUST receive `401`.

#### Scenario: Student Regular Premium appear when flagged subscribable

- **WHEN** Student, Regular, and Premium packages are active and subscribable and a verified customer lists plans
- **THEN** the response includes those three plans by `public_id` and name

#### Scenario: Inactive plan hidden from customers

- **WHEN** a plan is `is_subscribable=true` but `is_active=false`
- **THEN** it is absent from the customer catalog
