## ADDED Requirements

### Requirement: One non-cancelled meal package per order month

The system SHALL allow a verified customer at most one meal package order whose `order_status` is one of `pending`, `confirmed`, `active`, or `completed` for a given `order_month` (`YYYY-MM`). A second create attempt for the same customer and `order_month` MUST be rejected without creating an order. Cancelled orders MUST NOT block a new order for that month.

#### Scenario: Second package in the same month is rejected

- **WHEN** a verified customer already has a non-cancelled meal package order for `2026-07` and attempts to create another package whose computed `order_month` is `2026-07`
- **THEN** the system rejects the request with a validation error indicating they already have a meal package for this month and does not create a new order

#### Scenario: Cancelled package allows a replacement in the same month

- **WHEN** a verified customer’s only order for `2026-07` is `cancelled` and they create a new meal package order for that month
- **THEN** the system creates the new order successfully

#### Scenario: Different calendar months are allowed

- **WHEN** a verified customer has a non-cancelled order for `2026-07` and places an order whose `order_month` is `2026-08`
- **THEN** the system creates the August order successfully

### Requirement: Month lock is enforced in the order creation service

The system MUST evaluate same-month exclusivity inside the meal order creation workflow used by the customer API (not only in the HTTP layer), so every create path applies the same rule.

#### Scenario: Service-level create respects month lock

- **WHEN** `create_meal_order` is invoked for a customer who already has a locking order for the target `order_month`
- **THEN** the service raises a month-lock domain error and persists no new `Order` row
