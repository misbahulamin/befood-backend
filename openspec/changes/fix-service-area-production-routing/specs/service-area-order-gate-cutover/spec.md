## ADDED Requirements

### Requirement: Order gate is controllable via settings
The system SHALL honor `SERVICE_AREA_ORDER_GATE_ENABLED` so operators can disable the meal-order service-area assertion during production cutover without redeploying application code.

#### Scenario: Gate disabled skips assertion
- **WHEN** `SERVICE_AREA_ORDER_GATE_ENABLED` is `False`
- **AND** a customer creates a meal package order
- **THEN** the order service MUST NOT reject the order solely for service-area coverage

#### Scenario: Gate enabled enforces coverage
- **WHEN** `SERVICE_AREA_ORDER_GATE_ENABLED` is `True`
- **AND** a resolved delivery place lies outside every active hub (or lacks coordinates)
- **THEN** order create MUST fail with a service-area domain error code (`SERVICE_AREA_UNAVAILABLE` or `DELIVERY_LOCATION_REQUIRED`)

### Requirement: Safe production cutover order
Production cutover MUST enable the order gate only after at least one active service hub exists and delivery-place coordinates can be supplied for checkout.

#### Scenario: Enable after hubs exist
- **WHEN** operators set `SERVICE_AREA_ORDER_GATE_ENABLED=True` on production
- **THEN** at least one active `ServiceArea` hub MUST already exist
- **AND** customer order create for an in-radius delivery place with coordinates MUST succeed (subject to other existing order rules)

### Requirement: Order create surfaces machine-readable service-area error codes
When the gate rejects an order, the API response MUST expose a machine-readable `error_code` value that clients can branch on (`DELIVERY_LOCATION_REQUIRED` or `SERVICE_AREA_UNAVAILABLE`).

#### Scenario: Missing delivery coordinates
- **WHEN** the gate is enabled and a required delivery place has null latitude or longitude
- **THEN** order create MUST fail
- **AND** the client-visible error payload MUST include `DELIVERY_LOCATION_REQUIRED`

#### Scenario: Outside all hubs
- **WHEN** the gate is enabled and delivery coordinates are outside every active hub radius
- **THEN** order create MUST fail
- **AND** the client-visible error payload MUST include `SERVICE_AREA_UNAVAILABLE`
