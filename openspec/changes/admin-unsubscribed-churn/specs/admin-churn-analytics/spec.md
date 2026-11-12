# Spec Delta

## Purpose

Exposes verified-admin churn analytics for a date range so ops can measure churn rate, reasons, cohorts, and leading signals without ad-hoc SQL.

## ADDED Requirements

### Requirement: Analytics endpoint
The system SHALL provide `GET /api/v1/web/churn/analytics/?from=&to=` for verified admins. Missing or invalid date range MUST yield `400`. Timezone for period boundaries MUST be Asia/Dhaka.

#### Scenario: Valid period analytics
- **WHEN** a verified admin requests analytics with valid `from` and `to`
- **THEN** the response MUST include KPIs, breakdowns, time series, cohort retention, and leading signals sections

### Requirement: Period KPIs
Analytics MUST include: churned count in period, churn rate percent (churned ÷ active-at-period-start), net growth (new subscriptions − churned), win-back count and rate, at_risk count (current), never_subscribed count (current), average and median tenure days before churn, and revenue lost (sum of monthly plan value of churned subscriptions in period).

#### Scenario: Churn rate uses period-start active base
- **WHEN** period analytics are computed
- **THEN** churn_rate MUST use customers (or subscriptions, consistently documented) active at period start as the denominator

### Requirement: Breakdowns
Analytics MUST break down churned volume by `reason_code`, package and meal period, zone/location, tenure buckets (`0-7`, `8-14`, `15-30`, `31-60`, `60+` days), and `cancelled_by`.

#### Scenario: Reason breakdown
- **WHEN** multiple cancels with different reason codes occur in the period
- **THEN** `by_reason` MUST count each reason_code separately

### Requirement: Time series and cohorts
Analytics MUST include daily or weekly new-subscriptions vs cancels time series for the period, and cohort retention by start month showing percent still active after 7/14/30/60 days.

#### Scenario: Cohort retention points
- **WHEN** analytics are requested for a range covering at least one start-month cohort
- **THEN** each cohort row MUST include retention percentages for 7, 14, 30, and 60 days

### Requirement: Leading signals before churn
Analytics MUST report average meal-offs and low-balance block days in the 14 days before cancel for churned customers in the period, compared with the same metrics for currently active customers over an equivalent recent window.

#### Scenario: Leading signal comparison present
- **WHEN** the period has at least one churned customer
- **THEN** leading_signals MUST include churned vs active averages for meal-offs and low-balance blocks
