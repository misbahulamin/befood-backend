## ADDED Requirements

### Requirement: Admin can manage delivery schedules
The system SHALL allow a verified admin to create, list, retrieve, partially update, and hard-delete delivery schedule records. Each record MUST have a human-readable `name`, `start_time`, `end_time`, `is_active`, and `sort_order`, and MUST be identified in APIs by `public_id` (UUID), not integer primary key.

#### Scenario: Create a custom delivery type
- **WHEN** a verified admin POSTs a valid payload with `name` "Breakfast", `start_time` "08:00:00", `end_time` "10:00:00", `is_active` true, and `sort_order` 0
- **THEN** the system creates the record and returns `201` with the persisted fields including `public_id`

#### Scenario: List includes inactive schedules
- **WHEN** a verified admin GETs the admin delivery-schedules collection
- **THEN** the response includes both active and inactive schedules (subject to optional `is_active` / search filters)

#### Scenario: Update times and status
- **WHEN** a verified admin PATCHes an existing schedule’s `start_time`, `end_time`, `name`, `is_active`, or `sort_order`
- **THEN** the system persists only provided fields and returns `200` with the updated resource

#### Scenario: Hard delete
- **WHEN** a verified admin DELETEs a schedule by `public_id`
- **THEN** the system removes the row and returns `204`

#### Scenario: Unauthenticated admin access denied
- **WHEN** an unauthenticated or non-admin client calls an admin delivery-schedules write or list endpoint
- **THEN** the system returns `401` or `403`

### Requirement: Delivery schedule field validation
The system SHALL validate delivery schedule input as follows: `name` is required after trimming whitespace; `name` MUST be unique among schedules; `start_time` and `end_time` are required; `start_time` MUST be strictly earlier than `end_time` (same-day window only); equal start and end MUST be rejected. Overnight windows (end before or equal to start across midnight) MUST NOT be accepted in this version.

#### Scenario: Reject blank name
- **WHEN** an admin submits a schedule with empty or whitespace-only `name`
- **THEN** the system returns `400` with a field error on `name`

#### Scenario: Reject duplicate name
- **WHEN** an admin creates or renames a schedule to a `name` that already exists
- **THEN** the system returns `400` with a uniqueness error on `name`

#### Scenario: Reject end before or equal to start
- **WHEN** an admin submits `start_time` "22:00:00" and `end_time` "01:00:00", or equal start and end
- **THEN** the system returns `400` with a validation error indicating the window must be same-day with `start_time` &lt; `end_time`

#### Scenario: Accept valid same-day window
- **WHEN** an admin submits Lunch with `start_time` "12:00:00" and `end_time` "14:30:00"
- **THEN** validation succeeds

### Requirement: Times are Asia/Dhaka wall-clock values
The system SHALL store `start_time` and `end_time` as time-of-day values representing BeFood’s operational local timezone `Asia/Dhaka`, consistent with existing meal-off and menu-reveal `TimeField` conventions. The API MUST NOT require clients to send timezone offsets for these fields.

#### Scenario: Persist local wall-clock times
- **WHEN** an admin saves `start_time` "12:00:00" and `end_time` "14:30:00"
- **THEN** subsequent GET responses return those same time-of-day values without converting them as absolute UTC instants

### Requirement: Delivery schedules are independent of operational meal_period
The delivery schedule catalog MUST NOT alter, replace, or drive operational `meal_period` enums (`lunch` / `dinner`) used by orders, kitchen, meal-off, menu reveal, or delivery boards. Creating a schedule named "Breakfast" MUST NOT require backend enum changes for meal periods.

#### Scenario: New schedule does not change meal_period choices
- **WHEN** an admin creates an active schedule named "Sehri"
- **THEN** order/kitchen `meal_period` choice sets remain unchanged and no migration of operational period enums is required
