## Purpose

Verified customers can place a meal package order for a client-selected meal month (current local month through the next 12 months), with `order_month` persisted and service dates computed for that target month.

## Requirements

### Requirement: Customer can create a meal order for a selected meal month

The system SHALL allow a verified customer to create a meal package order for a client-selected calendar meal month. The request MUST accept optional `year` and `month` integers identifying the target meal month. When both are omitted, the system MUST use the current local calendar month and existing “today”-based period behavior. When provided, both MUST be present and valid. The system MUST persist the selected month on the order as `order_month` in `YYYY-MM` form and MUST compute `order_start_date`, `order_end_date`, `service_days_count`, and deliveries for that target month according to the meal’s `meal_type`.

#### Scenario: Create order for a future month

- **WHEN** a verified customer creates an order with `year` and `month` set to next calendar month (within the allowed window) for an eligible meal
- **THEN** the system creates the order with `order_month` equal to that month and service dates anchored to that month

#### Scenario: Omit year and month uses current month

- **WHEN** a verified customer creates an order without `year` and `month`
- **THEN** the system creates the order using the current local month / today’s period rules (backward compatible)

#### Scenario: Partial year or month rejected

- **WHEN** a client supplies only `year` or only `month`
- **THEN** the system rejects the request with a validation error and creates no order

### Requirement: Selected meal month must be within the allowed window

The system SHALL accept only meal months from the current local calendar month through the next 12 calendar months inclusive (13 selectable months). Months outside that window MUST be rejected without creating an order.

#### Scenario: Month within window accepted

- **WHEN** a verified customer selects a month that is the current month or up to 12 months ahead
- **THEN** the system proceeds with further eligibility checks for that month

#### Scenario: Month beyond twelve months ahead rejected

- **WHEN** a verified customer selects a month more than 12 months after the current local month
- **THEN** the system rejects the request with a validation error and creates no order

#### Scenario: Past month rejected

- **WHEN** a verified customer selects a calendar month before the current local month
- **THEN** the system rejects the request with a validation error and creates no order

### Requirement: Month lock and wallet minimum apply to the selected meal month

The system MUST enforce the existing same-month package lock against the **selected** `order_month`, and MUST enforce the existing wallet minimum balance gate, before creating the order. A non-cancelled package in a different `order_month` MUST NOT block creation for the selected month.

#### Scenario: Existing package in another month allows create

- **WHEN** a verified customer has a non-cancelled order for `2026-07` and creates an eligible order for `2026-08`
- **THEN** the system creates the August order successfully (subject to publish and wallet rules)

#### Scenario: Existing package in selected month blocks create

- **WHEN** a verified customer already has a non-cancelled order for `2026-08` and attempts another order for `2026-08`
- **THEN** the system rejects with the month-lock error and creates no order

#### Scenario: Insufficient wallet blocks create for selected month

- **WHEN** a verified customer selects a valid published month but wallet balance is below the configured minimum
- **THEN** the system rejects with the insufficient-balance error and creates no order
