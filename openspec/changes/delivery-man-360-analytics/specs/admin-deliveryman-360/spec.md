## ADDED Requirements

### Requirement: Admin can list Delivery Men with performance KPIs
The system SHALL provide a verified-admin API `GET /api/v1/web/delivery-men/` that lists Delivery Man (`RiderProfile`) accounts with pagination. Each item MUST include identity fields (`public_id`, name, phone), assigned zone summary (nullable), status/availability flags, and delivery count KPIs for **today**, **current calendar month**, and **lifetime** (completed logistics or meal-delivered stops attributed to that rider). Unauthenticated or non-verified-admin callers MUST be rejected with `401` or `403`.

#### Scenario: List returns KPI fields
- **WHEN** a verified admin requests `GET /api/v1/web/delivery-men/`
- **THEN** the system responds `200` with a paginated list where each item includes today, month, and lifetime delivery totals

#### Scenario: Non-admin cannot list analytics directory
- **WHEN** an unauthenticated client or non-verified-admin requests the Delivery Men analytics list
- **THEN** the system responds `401` or `403` and does not return Delivery Man performance data

### Requirement: Admin can load lean Delivery Man analytics overview
The system SHALL provide `GET /api/v1/web/delivery-men/{public_id}/` that returns a lean overview for one Delivery Man: name, phone, assigned zone, joining date (`created_at` or documented equivalent), account/operational status, current availability, plus nested **today**, **month**, and **lifetime** metric objects. Today and month metrics MUST break out lunch count, dinner count, and total completed deliveries. Lifetime metrics MUST include total completed deliveries, distinct customers served, and distinct zones covered when data exists. The overview MUST NOT embed paginated delivery history rows, full timeline arrays, or unbounded route lists.

#### Scenario: Overview returns today month lifetime cards
- **WHEN** a verified admin requests analytics overview for an existing Delivery Man `public_id`
- **THEN** the system responds `200` with overview identity fields and `today`, `month`, and `lifetime` metric objects without embedding history arrays

#### Scenario: Unknown Delivery Man overview
- **WHEN** a verified admin requests overview for a `public_id` that does not exist
- **THEN** the system responds `404 Not Found`

### Requirement: Admin can list filtered Delivery Man delivery history
The system SHALL provide `GET /api/v1/web/delivery-men/{public_id}/deliveries/` returning paginated delivery history attributed to that rider. Each row MUST expose service date, time (delivered or marked timestamp), customer display name, customer phone (when available), location label, zone, meal type (`lunch`/`dinner`), meal and/or logistics status, delivered-by identity, and delivery duration when computable. The endpoint MUST support allowlisted filters: date range or presets (`today`, `yesterday`, `this_week`, `this_month`), `meal_period`, `zone_public_id`, and status. Unsupported filter keys MUST be rejected with `400`. Results MUST use deterministic ordering (default newest first with a unique tie-breaker).

#### Scenario: History filtered by meal period and date preset
- **WHEN** a verified admin requests deliveries for a rider with `meal_period=dinner` and `preset=today`
- **THEN** the system returns only that rider’s dinner stops for today, paginated

#### Scenario: History rejects unknown filter
- **WHEN** a verified admin supplies an unsupported query parameter
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin can view Delivery Man activity timeline
The system SHALL provide `GET /api/v1/web/delivery-men/{public_id}/timeline/` that returns ordered logistics activity events for a requested date (default today in the project business timezone). Each event MUST include timestamp, status or event type, optional customer/delivery reference, and optional coordinates when stored.

#### Scenario: Timeline for today
- **WHEN** a verified admin requests the timeline for a Delivery Man without a date (or with today’s date)
- **THEN** the system returns that rider’s activity events for today in chronological order

### Requirement: Admin can view delivery route sequence for a meal window
The system SHALL provide `GET /api/v1/web/delivery-men/{public_id}/route/` requiring `service_date` and `meal_period`. The response MUST include an ordered list of stops for the rider’s zone workload (or attributed stops) with sequence number, customer/location labels, coordinates when available, and stop status, suitable for map markers and route lines on the client. A documented hub/starting-point placeholder MAY be included as sequence zero.

#### Scenario: Route for dinner on a service date
- **WHEN** a verified admin requests route with a valid `service_date` and `meal_period=dinner` for a zone-assigned rider
- **THEN** the system responds `200` with an ordered stop list including sequence numbers

#### Scenario: Route missing required query params
- **WHEN** a verified admin omits `service_date` or `meal_period`
- **THEN** the system responds `400 Bad Request`

### Requirement: Admin can compare Delivery Man rankings
The system SHALL provide `GET /api/v1/web/delivery-men/rankings/` (or equivalent collection action) that returns comparable metrics across Delivery Men for an allowlisted period filter: total deliveries, average delivery time, completion rate, and failed delivery count. Results MUST be paginated or capped with a documented maximum and deterministic sort (default by total deliveries descending).

#### Scenario: Ranking by today’s totals
- **WHEN** a verified admin requests rankings with `preset=today`
- **THEN** the system returns Delivery Men with today’s total delivery, average delivery time, completion rate, and failed count fields
