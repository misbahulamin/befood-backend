# Spec Delta

## MODIFIED Requirements

### Requirement: Admin customer filters

The system SHALL support allowlisted filters on the customer list for: active vs inactive account (`User.is_active`), email verification status, whether the customer has an active order, package (meal category) association for active-order customers, registration date range on `User.date_joined`, subscription lifecycle (`lifecycle` = `active` | `at_risk` | `unsubscribed` | `never_subscribed` | `won_back`), churn date range (`churned_from` / `churned_to`), cancel reason (`cancel_reason`), and package filter for last/active subscription (`package`). Invalid enum values or unknown filter keys MUST be rejected with `400 Bad Request` when validation is enabled. Collections MUST use deterministic ordering with a unique tie-breaker. Sort allowlist MUST include churn date newest/oldest and tenure in addition to existing sorts.

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

#### Scenario: Filter by lifecycle unsubscribed

- **WHEN** a verified admin lists customers with `lifecycle=unsubscribed`
- **THEN** only customers classified `unsubscribed` by the shared lifecycle rules MUST be returned

#### Scenario: Filter by cancel reason

- **WHEN** a verified admin lists customers with `cancel_reason=food_taste`
- **THEN** only customers whose latest cancellation reason_code is `food_taste` MUST be returned

#### Scenario: Filter by churn date range

- **WHEN** a verified admin lists customers with `churned_from` and `churned_to`
- **THEN** only customers whose churn date falls in that inclusive Asia/Dhaka range MUST be returned

#### Scenario: Sort by churn date newest

- **WHEN** a verified admin lists customers with the churn-date-newest sort
- **THEN** results MUST be ordered by churn date descending with a unique tie-breaker

#### Scenario: Unsupported filter rejected

- **WHEN** a verified admin supplies an unknown filter field or invalid enum value
- **THEN** the system responds `400 Bad Request`

## ADDED Requirements

### Requirement: Customer list lifecycle enrichment
Each customer list row MUST include `lifecycle`, `last_subscription_package`, `churn_date` (nullable), `tenure_days` (nullable), `total_meals_delivered`, `last_cancel_reason` (nullable), and `wallet_balance` (nullable/string per existing money conventions).

#### Scenario: Unsubscribed row enrichment
- **WHEN** a verified admin lists an unsubscribed customer
- **THEN** the row MUST include non-null `lifecycle=unsubscribed`, `churn_date`, and `last_cancel_reason` when a cancellation reason exists (including backfilled `unknown`)
