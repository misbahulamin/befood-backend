## MODIFIED Requirements

### Requirement: Admin can list successful and in-progress orders

The system SHALL keep a verified-admin web collection of **historical** meal package orders for audit. Live mess operations MUST use the admin subscription collection. Historical list remains paginated and permission-gated.

#### Scenario: Admin lists orders after customer purchase

- **WHEN** an authorized admin requests the admin historical order list
- **THEN** previously created orders MUST appear with package snapshots, status, dates, and delivery progress summary fields
- **AND** a newly created subscription MUST appear on the admin **subscription** list, not as a new monthly order

#### Scenario: Unauthenticated admin list denied

- **WHEN** an unauthenticated client requests the admin order list
- **THEN** the system MUST respond with `401 Unauthorized`

#### Scenario: Non-admin authenticated user denied

- **WHEN** an authenticated customer without admin permission requests the admin order list
- **THEN** the system MUST respond with `403 Forbidden`

### Requirement: Admin order filtering

The system SHALL continue to support filtering **historical** admin orders by meal type snapshot, order status, activity, order month, and date ranges. Live subscriber filtering is defined by `admin-subscription-management`.

#### Scenario: Filter by meal type daily

- **WHEN** an admin lists historical orders with `meal_type=daily`
- **THEN** only orders whose `meal_type_snapshot` is `daily` MUST be returned

#### Scenario: Filter by meal type monthly

- **WHEN** an admin lists historical orders with `meal_type=monthly`
- **THEN** only monthly package orders MUST be returned

#### Scenario: Filter active orders

- **WHEN** an admin lists historical orders with `activity=active`
- **THEN** only historical orders that are currently within their service window and not completed/cancelled MUST be returned

#### Scenario: Filter inactive orders

- **WHEN** an admin lists historical orders with `activity=inactive`
- **THEN** completed, cancelled, and out-of-window historical orders MUST be included per the activity definition and active ones MUST be excluded

#### Scenario: Filter by order month

- **WHEN** an admin lists historical orders with `order_month=YYYY-MM`
- **THEN** only orders for that month key MUST be returned

#### Scenario: Unsupported filter rejected

- **WHEN** an admin supplies an unknown filter field or invalid enum value
- **THEN** the system MUST respond with `400 Bad Request` and MUST NOT silently ignore the bad parameter when validation is enabled for that field

### Requirement: Admin order detail with deliveries

The system SHALL provide an admin historical order detail representation including delivery slots and progress counters. Admin detail for live service MUST be the subscription detail.

#### Scenario: Admin retrieves order detail

- **WHEN** an authorized admin retrieves a historical order by id
- **THEN** the response MUST include customer reference, package snapshots, status, period fields, expected/delivered/remaining counts, and the delivery slot list (paginated or bounded for the order window)
