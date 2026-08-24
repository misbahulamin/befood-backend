## MODIFIED Requirements

### Requirement: Customer sees own successful orders only

The system SHALL allow an authenticated verified customer to list and retrieve only their own **historical** meal package orders (read-only). New service status MUST be read from the caller’s subscription APIs. Historical list MUST NOT include other customers’ orders.

#### Scenario: Customer lists my orders

- **WHEN** a customer with existing historical orders calls the my-orders (or equivalent) endpoint
- **THEN** the system MUST return that customer’s historical orders and MUST NOT include other customers’ orders

#### Scenario: Customer cannot retrieve another customer order

- **WHEN** a customer requests an order id owned by a different customer
- **THEN** the system MUST respond with `404 Not Found` or `403 Forbidden` without leaking the other order’s payload

### Requirement: Customer delivery progress is read-only

The system SHALL expose delivery progress on the customer **current subscription** (and historical order detail) without allowing the customer to mark deliveries.

#### Scenario: Customer views progress on active package

- **WHEN** a customer retrieves their current active subscription detail
- **THEN** the response MUST include expected delivery count for generated slots, delivered count, remaining count, and current status
- **AND** the response MUST NOT require the customer to perform mark-delivered to see progress

#### Scenario: Current package null when none

- **WHEN** a customer has no active subscription
- **THEN** the current-subscription (or current-package compatibility) endpoint MUST return a null payload with a clear message
