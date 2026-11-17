# Spec Delta

## Purpose

Verified admins manage Test Meal orders through paginated list/detail APIs with search and filters, and retrieve chart-ready analytics aggregations for operations and reporting.

## ADDED Requirements

### Requirement: Admin Test Meal order list and detail

The system SHALL provide verified-admin list and detail endpoints for Test Meal orders exposing at least: order public id, customer name/phone/id, package name, menu/slot info, delivery date, meal period, delivery window, address and zone, meal price, box charge, total, payment status, order status, special instructions, created/delivered times, and subscription conversion indicators. Customers MUST be denied. Pagination MUST be enforced with a default and maximum page size.

#### Scenario: Admin lists orders

- **WHEN** a verified admin requests the Test Meal order list
- **THEN** a paginated collection of Test Meal orders is returned with the required fields

#### Scenario: Admin views detail

- **WHEN** a verified admin requests a Test Meal order by public id
- **THEN** the full detail payload is returned

#### Scenario: Customer denied admin list

- **WHEN** a verified customer calls the admin Test Meal list
- **THEN** the system returns `401` or `403`

### Requirement: Admin search and filters

Admin list MUST support search by customer name, phone, and order public id, and filters by date range, package, meal period, order status, payment status, delivery zone, and converted/not converted. Unsupported filter values MUST be rejected with `400` rather than silently ignored when validation applies.

#### Scenario: Filter unpaid lunch orders

- **WHEN** an admin filters by `meal_period=lunch` and `payment_status=unpaid`
- **THEN** only matching Test Meal orders are returned

#### Scenario: Search by phone

- **WHEN** an admin searches by a customer phone fragment
- **THEN** matching customer Test Meal orders are included

### Requirement: Admin analytics endpoint

The system SHALL provide a verified-admin analytics endpoint that returns customer/order metrics, quota metrics, payment/revenue metrics, and chart-ready series for daily orders, deliveries, revenue, new Test Meal customers, conversions, package popularity, lunch/dinner distribution, conversion by package/zone, and time-to-conversion distribution. Metrics MUST use consistent definitions and avoid double counting. Division by zero MUST be avoided for rates.

#### Scenario: Empty range safe conversion rate

- **WHEN** an admin requests analytics for a range with zero delivered Test Meal customers
- **THEN** conversion rate is reported safely (zero or null per contract) without server error

#### Scenario: Daily series returned

- **WHEN** an admin requests analytics with a date range containing orders
- **THEN** the response includes daily aggregated series suitable for charts
