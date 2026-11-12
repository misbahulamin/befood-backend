# Spec Delta

## Purpose

Extends the ops dashboard summary with additive churn KPIs so admins see unsubscribed, churn rate, at-risk, and win-back signals in one round-trip.

## ADDED Requirements

### Requirement: Dashboard summary churn fields
`GET /api/v1/web/dashboard/summary/` MUST include additive integer/number fields: `unsubscribed_this_month`, `churn_rate_this_month`, `at_risk_count`, `won_back_this_month`, computed with Asia/Dhaka month boundaries and the shared lifecycle rules. Existing summary fields MUST remain unchanged.

#### Scenario: Additive fields present
- **WHEN** a verified admin fetches dashboard summary
- **THEN** the payload MUST include `unsubscribed_this_month`, `churn_rate_this_month`, `at_risk_count`, and `won_back_this_month` without removing existing keys

#### Scenario: Month-scoped unsubscribed count
- **WHEN** customers churn within the current Asia/Dhaka calendar month
- **THEN** `unsubscribed_this_month` MUST count those customers (per documented unique-customer rule)
