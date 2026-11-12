# Spec Delta

## Purpose

Captures structured cancellation reasons on every subscription cancel so ops can analyze churn drivers and backfill historical cancels without inventing fake reasons.

## ADDED Requirements

### Requirement: Persist cancellation reason rows
The system SHALL store one `SubscriptionCancellation` per cancel event with subscription FK, customer FK, required `reason_code`, optional `reason_text`, `cancelled_by` in `{customer, admin, system}`, and `created_at`.

#### Scenario: Customer cancel writes reason
- **WHEN** a customer successfully cancels with `reason_code=price_too_high` and optional `reason_text`
- **THEN** a `SubscriptionCancellation` row MUST exist with those values and `cancelled_by=customer`

#### Scenario: Admin cancel writes reason
- **WHEN** a verified admin cancels a subscription with a valid `reason_code`
- **THEN** a `SubscriptionCancellation` row MUST exist with `cancelled_by=admin`

#### Scenario: System auto-cancel
- **WHEN** the system auto-cancels a subscription (expiry or low-balance policy path)
- **THEN** the cancellation row MUST use `cancelled_by=system` and a documented reason_code

### Requirement: Allowed reason codes
`reason_code` MUST be one of: `price_too_high`, `food_taste`, `food_quantity`, `delivery_late`, `delivery_area_not_covered`, `moving_away`, `exam_or_vacation`, `cooking_myself`, `switched_competitor`, `wallet_topup_hassle`, `app_problem`, `temporary_pause`, `other`, plus migration-only `unknown` for backfilled historical cancels.

#### Scenario: Invalid reason rejected
- **WHEN** a cancel request sends an unsupported `reason_code`
- **THEN** the system MUST respond `422` and MUST NOT cancel the subscription

### Requirement: Reason required on interactive cancels
Customer self-cancel and admin cancel endpoints MUST require `reason_code`. `reason_text` MAY be omitted. Omitting `reason_code` MUST NOT cancel.

#### Scenario: Missing reason_code
- **WHEN** a customer posts cancel without `reason_code`
- **THEN** the response MUST be `422` and subscription status MUST remain `active`

### Requirement: Historical backfill as unknown
Existing cancelled subscriptions without a reason row MUST be backfilled with `reason_code=unknown` during migration. Interactive cancel APIs MUST NOT accept `unknown` from clients.

#### Scenario: Backfill existing cancels
- **WHEN** migrations run against cancelled subscriptions that lack reason rows
- **THEN** each MUST receive a `SubscriptionCancellation` with `reason_code=unknown`
