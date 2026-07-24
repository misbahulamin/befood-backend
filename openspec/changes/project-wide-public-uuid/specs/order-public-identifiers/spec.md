## ADDED Requirements

### Requirement: Order has public UUID identity

The system SHALL store a unique `public_id` on every `Order`. Customer and web order detail/list/cancel/current-package responses MUST identify orders by `public_id` and MUST NOT expose integer order `id` on customer serializers after cutover. Order URL lookup MUST use `public_id`.

#### Scenario: Customer lists orders with public_id

- **WHEN** a customer lists orders
- **THEN** each order includes `public_id` and does not include integer `id`

#### Scenario: Order detail by UUID

- **WHEN** a client retrieves `GET /orders/<order_public_id>/`
- **THEN** the matching order is returned

#### Scenario: Integer order path fails

- **WHEN** a client uses the previous integer order path after cutover
- **THEN** the order is not found

### Requirement: OrderDelivery has public UUID identity

The system SHALL store a unique `public_id` on every `OrderDelivery`. Nested delivery objects in order detail and meal-off / mark-delivery paths MUST use delivery `public_id`. Today-board and related payloads MUST reference `order_public_id` / delivery `public_id` instead of integer ids on customer-facing and standard web board contracts after cutover.

#### Scenario: Meal-off uses delivery public_id

- **WHEN** a customer requests meal-off for a delivery
- **THEN** the path identifies the delivery by `public_id` under the order `public_id`

#### Scenario: Nested deliveries expose public_id

- **WHEN** order detail returns deliveries
- **THEN** each delivery includes `public_id` and does not include integer `id` on customer serializers

### Requirement: Cross-resource references stay UUID

Customer payloads that reference meals MUST continue using `meal_public_id`. Payloads that reference orders from other customer surfaces (e.g. today-menu) MUST use `order_public_id`.

#### Scenario: Today-menu order reference

- **WHEN** today-menu returns packages for a customer
- **THEN** each package identifies the order with `order_public_id` (not integer `order_id`)
