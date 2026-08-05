## ADDED Requirements

### Requirement: Admin can list successful and in-progress orders
The system SHALL provide an admin/web order collection endpoint that returns paginated orders placed by customers, including confirmed, active, completed, and cancelled records as filtered.

#### Scenario: Admin lists orders after customer purchase
- **WHEN** a verified customer successfully creates an order and an authorized admin requests the admin order list
- **THEN** that order MUST appear in the list with package snapshots, status, dates, and delivery progress summary fields

#### Scenario: Unauthenticated admin list denied
- **WHEN** an unauthenticated client requests the admin order list
- **THEN** the system MUST respond with `401 Unauthorized`

#### Scenario: Non-admin authenticated user denied
- **WHEN** an authenticated customer without admin permission requests the admin order list
- **THEN** the system MUST respond with `403 Forbidden`

### Requirement: Admin order filtering
The system SHALL support filtering admin orders by meal type, order status, active/inactive activity, order month, and date ranges.

#### Scenario: Filter by meal type daily
- **WHEN** an admin lists orders with `meal_type=daily`
- **THEN** only orders whose `meal_type_snapshot` is `daily` MUST be returned

#### Scenario: Filter by meal type monthly
- **WHEN** an admin lists orders with `meal_type=monthly`
- **THEN** only monthly package orders MUST be returned

#### Scenario: Filter active orders
- **WHEN** an admin lists orders with `activity=active`
- **THEN** only orders that are currently within their service window and not completed/cancelled MUST be returned

#### Scenario: Filter inactive orders
- **WHEN** an admin lists orders with `activity=inactive`
- **THEN** completed, cancelled, and out-of-window orders MUST be included per the activity definition and active ones MUST be excluded

#### Scenario: Filter by order month
- **WHEN** an admin lists orders with `order_month=YYYY-MM`
- **THEN** only orders for that month key MUST be returned

#### Scenario: Unsupported filter rejected
- **WHEN** an admin supplies an unknown filter field or invalid enum value
- **THEN** the system MUST respond with `400 Bad Request` and MUST NOT silently ignore the bad parameter when validation is enabled for that field

### Requirement: Admin order detail with deliveries
The system SHALL provide an admin order detail representation including delivery slots and progress counters.

#### Scenario: Admin retrieves order detail
- **WHEN** an authorized admin retrieves an order by id
- **THEN** the response MUST include customer reference, package snapshots, status, period fields, expected/delivered/remaining counts, and the delivery slot list (paginated or bounded for the order window)
