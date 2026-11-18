# Spec Delta

## MODIFIED Requirements

### Requirement: Admin summary email after threshold cron

After each wallet-threshold cron execution (non-dry-run), the system SHALL email a structured low-balance report to verified admin recipients (same resolution pattern as wallet funding admin notifications). The email MUST use a professional layout with an Excel-like tabular presentation of affected users. Affected users MUST be limited to customers with an active meal subscription who meet reminder or meal-stop threshold rules for that run. The reported user count MUST match that filtered set.

#### Scenario: Summary includes required columns

- **WHEN** a cron run finds one or more active-subscriber customers who are below the reminder threshold and/or meal-stopped
- **THEN** each admin recipient receives an email whose table includes columns for user name, phone number, package name, current wallet balance, address, and meal status (for example `Low Balance` or `Meal Stopped`)

#### Scenario: No affected users

- **WHEN** a cron run finds no active-subscriber customers below the reminder or meal-stop thresholds and none newly resumed requiring reporting
- **THEN** the system either sends a short “no low-balance users” summary or skips the email according to the documented implementation choice, and MUST NOT fail the cron run

#### Scenario: Non-active customers omitted from report

- **WHEN** customers without an active meal subscription (cancelled or never subscribed) have low wallet balances and/or a leftover meal-service block flag
- **THEN** those customers do not appear in the admin low-balance report table and are not counted in the report’s user total

## ADDED Requirements

### Requirement: Report package reflects active subscription

Every row in the admin low-balance report MUST correspond to a customer with an active meal subscription, and the package column MUST show that subscription’s package name rather than an empty or `N/A` placeholder caused by missing active subscription.

#### Scenario: Package is present for listed users

- **WHEN** an admin receives a low-balance users report that lists one or more customers
- **THEN** each listed row has a non-placeholder package name from the customer’s active meal subscription
