# Spec Delta

## Purpose

Provides a verified-admin paginated unsubscribed/churn customer collection with shared lifecycle filters and CSV export for win-back operations.

## ADDED Requirements

### Requirement: Unsubscribed customers collection
The system SHALL provide `GET /api/v1/web/churn/customers/` for verified admins returning a paginated list of customers whose lifecycle is `unsubscribed` by default (or matching supplied lifecycle filters). Unauthenticated callers MUST receive `401`; non-admin callers MUST receive `403`.

#### Scenario: Default unsubscribed list
- **WHEN** a verified admin calls `GET /api/v1/web/churn/customers/` without lifecycle override
- **THEN** only `unsubscribed` customers MUST be returned in deterministic paginated order

### Requirement: Shared churn filters
The collection MUST support allowlisted filters: `lifecycle`, `churned_from`, `churned_to`, `cancel_reason`, `package`, search `q`, and sorts including churn date newest/oldest and tenure. Unknown keys or invalid enums MUST yield `400`.

#### Scenario: Filter by cancel reason
- **WHEN** admin requests `cancel_reason=price_too_high`
- **THEN** only customers whose latest cancellation reason_code matches MUST be returned

#### Scenario: Churn date range
- **WHEN** admin supplies `churned_from` and `churned_to`
- **THEN** only customers whose churn date falls in the inclusive Asia/Dhaka range MUST be returned

### Requirement: Row enrichment fields
Each row MUST include at least: customer identity fields used on admin customers list, `lifecycle`, `last_subscription_package`, `churn_date`, `tenure_days`, `total_meals_delivered`, `last_cancel_reason`, `wallet_balance`, and latest follow-up status when present.

#### Scenario: Enriched unsubscribed row
- **WHEN** an unsubscribed customer is listed
- **THEN** the payload MUST include churn_date, tenure_days, last_cancel_reason, and last_subscription_package

### Requirement: CSV export
When `format=csv` is supplied, the endpoint MUST return a CSV download of the filtered result set (or a documented export of the same filter scope) with Content-Disposition attachment. Non-admin access rules remain unchanged.

#### Scenario: CSV export
- **WHEN** a verified admin requests `GET /api/v1/web/churn/customers/?format=csv` with filters
- **THEN** the response MUST be CSV with matching filtered rows
