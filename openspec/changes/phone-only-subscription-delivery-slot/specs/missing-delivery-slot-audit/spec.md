## ADDED Requirements

### Requirement: Read-only report of active subscriptions missing delivery slots

The system SHALL provide a read-only audit mechanism (management command and/or documented SQL) that lists or aggregates customers/subscriptions where status is ACTIVE and the count of related `OrderDelivery` rows is zero (or below an expected minimum for the horizon). The audit MUST NOT modify customers, subscriptions, emails, or deliveries.

#### Scenario: Report counts affected subscriptions

- **WHEN** an operator runs the missing-slot audit in read-only mode
- **THEN** the system reports totals such as active subscriptions, phone-only subset, and missing-slot subset without writing to the database

### Requirement: Audit distinguishes unpublished menu from other causes

The missing-slot audit MUST classify each (or summarize cohorts of) missing-slot ACTIVE subscription as at least: (a) no published menu for meal in current/next month horizon, or (b) published menu present—needs further investigation. Classification MUST be informational only.

#### Scenario: Unpublished menu cohort identified

- **WHEN** an ACTIVE subscription has zero deliveries and no published schedule for its meal in the ensure horizon months
- **THEN** the audit marks or counts that case under the unpublished-menu cohort

#### Scenario: Published menu but still missing slots flagged

- **WHEN** an ACTIVE subscription has zero deliveries despite a published schedule for a horizon month
- **THEN** the audit marks or counts that case under a separate investigation cohort

### Requirement: No destructive remediation in the audit tool

The audit tool MUST NOT backfill emails, reset subscriptions, rewrite orders, or invent delivery rows as a side effect of reporting. Remediation of missing slots MUST remain a separate, explicit ensure/publish operation.

#### Scenario: Dry-run audit has no writes

- **WHEN** the audit command completes successfully
- **THEN** no customer, subscription, or delivery rows are created, updated, or deleted by that command
