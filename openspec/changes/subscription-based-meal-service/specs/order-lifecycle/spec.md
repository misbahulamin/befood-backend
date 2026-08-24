## MODIFIED Requirements

### Requirement: Order status lifecycle by package rules

The system SHALL retain meal package **historical** orders through statuses `pending`, `confirmed`, `active`, `completed`, and `cancelled` for rows created before subscription launch. New customer meal service MUST NOT start by creating an `Order`. Ongoing commercial entitlement is `CustomerSubscription` (`active` until cancel). Historical orders MAY still complete or stay completed according to existing delivery progress; they MUST NOT be used to start a new month of service.

#### Scenario: Successful order starts as confirmed

- **WHEN** a historical meal package order already exists from before subscription launch
- **THEN** that order keeps its stored `order_status` and remains visible to authorized admins in historical management queries

#### Scenario: Order becomes active on start date

- **WHEN** a historical `confirmed` order has local business date on or after `order_start_date` and is not cancelled
- **THEN** the system MAY still transition that historical order to `active` during migration/sync
- **AND** new customers MUST receive service via an `active` subscription instead of a new confirmed order

#### Scenario: Daily order completes after one delivery

- **WHEN** a historical `daily` package order has its single expected delivery marked `delivered`
- **THEN** that historical order MUST transition to `completed` and MUST no longer accept further deliveries

#### Scenario: Multi-day order completes when quota finished

- **WHEN** every expected delivery slot for a historical non-daily order is in a terminal status (`delivered`, `skipped`, or `missed`)
- **THEN** that historical order MUST transition to `completed`
- **AND** an `active` subscription MUST NOT complete for that reason

#### Scenario: Invalid status transition rejected

- **WHEN** a client requests a status change that is not allowed by the transition map
- **THEN** the system MUST reject the change with a validation/conflict error and MUST leave the previous status unchanged

## REMOVED Requirements

### Requirement: Month lock preserved for non-cancelled packages

**Reason:** Same-month package exclusivity is replaced by at most one active subscription per customer.
**Migration:** Use `customer-meal-subscription` uniqueness. Customer meal-order create is retired; do not enforce `order_month` lock on new service.
