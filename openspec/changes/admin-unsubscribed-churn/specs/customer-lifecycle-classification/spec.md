# Spec Delta

## Purpose

Defines mutually exclusive customer subscription lifecycle states and churn date rules so every admin list, analytics, and dashboard endpoint classifies customers the same way in Asia/Dhaka business time.

## ADDED Requirements

### Requirement: Shared lifecycle states
The system SHALL classify each registered customer into exactly one lifecycle value: `never_subscribed`, `unsubscribed`, `at_risk`, `won_back`, or `active`, using Asia/Dhaka business calendar dates.

#### Scenario: Never subscribed
- **WHEN** a customer has zero `CustomerSubscription` rows
- **THEN** lifecycle MUST be `never_subscribed`

#### Scenario: Unsubscribed
- **WHEN** a customer has at least one subscription ever AND has no subscription with status `active`
- **THEN** lifecycle MUST be `unsubscribed`

#### Scenario: At risk takes precedence over active and won_back
- **WHEN** a customer has an active subscription AND meets any at-risk rule
- **THEN** lifecycle MUST be `at_risk` (not `active` or `won_back`)

#### Scenario: Won back
- **WHEN** a customer has an active subscription, is not at_risk, AND has at least one earlier cancelled subscription whose churn date is before the current active subscription `started_on`
- **THEN** lifecycle MUST be `won_back`

#### Scenario: Active
- **WHEN** a customer has an active subscription and is not at_risk and is not won_back
- **THEN** lifecycle MUST be `active`

### Requirement: Churn date definition
For an unsubscribed customer, churn date MUST be the latest cancelled subscription's `cancel_effective_on`, falling back to the local Asia/Dhaka date of `cancelled_at` when `cancel_effective_on` is null.

#### Scenario: Prefer cancel_effective_on
- **WHEN** the latest cancelled subscription has `cancel_effective_on` set
- **THEN** churn date MUST equal that date

#### Scenario: Fallback to cancelled_at
- **WHEN** `cancel_effective_on` is null and `cancelled_at` is set
- **THEN** churn date MUST equal the Asia/Dhaka calendar date of `cancelled_at`

### Requirement: At-risk rules
A customer with an active subscription MUST be `at_risk` when any of the following holds in Asia/Dhaka business time: (1) low-balance meal service was blocked on at least 3 of the last 7 service days; (2) meal-off (customer or admin skip) occurred on at least 5 of the last 7 service days; (3) current wallet spendable balance is strictly below one day's meal cost for the active subscription.

#### Scenario: Low-balance silent churn
- **WHEN** an active subscriber was low-balance blocked on 3 or more of the last 7 service days
- **THEN** lifecycle MUST be `at_risk`

#### Scenario: Frequent meal-offs
- **WHEN** an active subscriber has meal-off skips on 5 or more of the last 7 service days
- **THEN** lifecycle MUST be `at_risk`

#### Scenario: Wallet below one day cost
- **WHEN** an active subscriber's spendable wallet balance is below one day's meal cost
- **THEN** lifecycle MUST be `at_risk`

### Requirement: Annotation-based evaluation
Lifecycle filters and list enrichment MUST be computable via database annotations / Exists subqueries (or equivalent set-based queries). Implementations MUST NOT classify customers with Python per-row loops over the full customer table for list/filter endpoints.

#### Scenario: Filter without N-plus-one classification loop
- **WHEN** an admin requests a paginated customer list filtered by `lifecycle=unsubscribed`
- **THEN** the response MUST return only matching customers without evaluating lifecycle in a Python loop over all customers
