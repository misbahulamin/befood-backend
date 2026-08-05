## Purpose

Customer visibility into their own successful orders, current package, and delivery progress.

## Requirements

### Requirement: Customer sees own successful orders only

The system SHALL allow an authenticated verified customer to list and retrieve only their own meal package orders after successful creation.

#### Scenario: Customer lists my orders

- **WHEN** a customer with existing orders calls the my-orders (or equivalent) endpoint
- **THEN** the system MUST return that customer’s orders and MUST NOT include other customers’ orders

#### Scenario: Customer cannot retrieve another customer order

- **WHEN** a customer requests an order id owned by a different customer
- **THEN** the system MUST respond with `404 Not Found` or `403 Forbidden` without leaking the other order’s payload

### Requirement: Customer delivery progress is read-only

The system SHALL expose delivery progress on the customer order detail (and optionally current-package) response without allowing the customer to mark deliveries.

#### Scenario: Customer views progress on active package

- **WHEN** a customer retrieves their active or current-month package detail
- **THEN** the response MUST include expected delivery count, delivered count, remaining count, and current status
- **AND** the response MUST NOT require the customer to perform mark-delivered to see progress

#### Scenario: Current package null when none

- **WHEN** a customer has no non-cancelled package for the current month
- **THEN** the current-package endpoint MUST return a null package payload with a clear message (existing contract additive-compatible)
