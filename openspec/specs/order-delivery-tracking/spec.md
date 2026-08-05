## Purpose

Per-order delivery slots, mark-delivered/skip, progress, and package completion rules. Period-specific slot generation for lunch/dinner/both is defined in `period-aware-order-slots`.

## Requirements

### Requirement: Expected delivery slots generated per package type

The system SHALL create expected `OrderDelivery` slots for each successful order according to meal type rules and the order’s meal-period snapshot (see `period-aware-order-slots`).

#### Scenario: Daily package gets one delivery slot

- **WHEN** a customer successfully orders a `daily` meal package with a single-period meal period (`lunch` or `dinner`)
- **THEN** the system MUST create exactly one delivery slot on `order_start_date` and MUST treat that package as closable after that single fulfillment

#### Scenario: Monthly package gets slots per calendar day and meal period

- **WHEN** a customer successfully orders a `monthly` meal package for a calendar month
- **THEN** the system MUST create slots for each day of that month according to `meal_period_snapshot` (`lunch` only, `dinner` only, or lunch and dinner for `both`)
- **AND** the total expected slot count MUST equal days-in-month × periods-per-day for that snapshot (for example 60 for a 30-day `both` month, 62 for a 31-day `both` month)

#### Scenario: Weekly package covers each day in the order window by meal period

- **WHEN** a customer successfully orders a `weekly` meal package
- **THEN** the system MUST create slots for each service day from `order_start_date` through `order_end_date` according to `meal_period_snapshot`

### Requirement: Mark delivery updates slot and progress

The system SHALL allow authorized admins (or kitchen operators with permission) to mark a scheduled delivery as `delivered` or `skipped`, and SHALL update order progress accordingly.

#### Scenario: Admin marks lunch delivered

- **WHEN** an authorized admin marks a `scheduled` delivery slot as `delivered`
- **THEN** the slot status MUST become `delivered`, progress counters MUST increase `delivered_count`, and an audit of who marked it MUST be stored

#### Scenario: Duplicate mark is idempotent or conflict-safe

- **WHEN** an admin marks a slot that is already `delivered`
- **THEN** the system MUST NOT create a second delivery event and MUST return a stable success or conflict response without corrupting counts

#### Scenario: Customer cannot mark delivery by default

- **WHEN** a customer calls a mark-delivery endpoint without admin/operator permission
- **THEN** the system MUST respond with `403 Forbidden` (or hide the route from customer clients)

### Requirement: Daily close after one delivery

The system SHALL close daily packages after one successful delivery so they become inactive for further fulfillment.

#### Scenario: Second delivery attempt on daily order rejected

- **WHEN** a daily order already has its expected slot delivered and is `completed`
- **THEN** further mark-delivery attempts MUST be rejected

### Requirement: Active days in current month

The system SHALL expose which service dates in the current calendar month remain relevant (scheduled or delivered) for an active multi-day package.

#### Scenario: Monthly package week/day activity for current month

- **WHEN** an admin or owning customer requests progress for a monthly package in the current month
- **THEN** the response MUST include expected total, delivered count, remaining count, and the set or list of active/relevant dates within the current month window
