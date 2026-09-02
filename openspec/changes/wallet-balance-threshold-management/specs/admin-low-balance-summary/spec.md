## ADDED Requirements

### Requirement: Admin summary email after threshold cron

After each wallet-threshold cron execution (non-dry-run), the system SHALL email a structured low-balance report to verified admin recipients (same resolution pattern as wallet funding admin notifications). The email MUST use a professional layout with an Excel-like tabular presentation of affected users.

#### Scenario: Summary includes required columns

- **WHEN** a cron run finds one or more customers who are below the reminder threshold and/or meal-stopped
- **THEN** each admin recipient receives an email whose table includes columns for user name, phone number, package name, current wallet balance, address, and meal status (for example `Low Balance` or `Meal Stopped`)

#### Scenario: No affected users

- **WHEN** a cron run finds no customers below the reminder or meal-stop thresholds and none newly resumed requiring reporting
- **THEN** the system either sends a short “no low-balance users” summary or skips the email according to the documented implementation choice, and MUST NOT fail the cron run

### Requirement: Report uses safe contact data

The admin summary MUST include the best available phone and address from the customer profile / delivery preferences without exposing secrets, wallet ledger internals, or authentication tokens.

#### Scenario: Missing optional fields

- **WHEN** a listed customer has no phone or address on file
- **THEN** the row still appears with empty or “N/A” placeholders for missing fields and populated fields remain accurate
