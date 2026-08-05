## ADDED Requirements

### Requirement: Order status lifecycle by package rules
The system SHALL manage meal package orders through statuses `pending`, `confirmed`, `active`, `completed`, and `cancelled`, and SHALL transition them according to package type and delivery progress.

#### Scenario: Successful order starts as confirmed
- **WHEN** a verified customer successfully creates a meal package order
- **THEN** the order MUST be stored with `order_status=confirmed` and MUST be visible to authorized admins in management queries

#### Scenario: Order becomes active on start date
- **WHEN** the local business date is on or after `order_start_date` and the order is `confirmed` and not cancelled
- **THEN** the system MUST transition the order to `active` (via lifecycle sync or before the first delivery action)

#### Scenario: Daily order completes after one delivery
- **WHEN** a `daily` package order has its single expected delivery marked `delivered`
- **THEN** the order MUST transition to `completed` and MUST no longer accept further deliveries

#### Scenario: Multi-day order completes when quota finished
- **WHEN** every expected delivery slot for a non-daily order is in a terminal status (`delivered`, `skipped`, or `missed`)
- **THEN** the order MUST transition to `completed`

#### Scenario: Invalid status transition rejected
- **WHEN** a client requests a status change that is not allowed by the transition map
- **THEN** the system MUST reject the change with a validation/conflict error and MUST leave the previous status unchanged

### Requirement: Month lock preserved for non-cancelled packages
The system SHALL continue to prevent a customer from holding more than one non-cancelled meal package in the same `order_month`.

#### Scenario: Second package in same month blocked
- **WHEN** a customer already has a non-cancelled order for `YYYY-MM` and attempts another create for that month
- **THEN** the system MUST reject the create with the existing month-lock error semantics
