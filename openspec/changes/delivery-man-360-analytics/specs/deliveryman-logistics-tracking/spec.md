## ADDED Requirements

### Requirement: OrderDelivery stores logistics and completion audit fields
The system SHALL persist logistics tracking fields associated with each `OrderDelivery` stop, including: attributed `delivery_man` / rider reference when known, zone and location references (or snapshots) used for analytics, `meal_period`, logistics status, `assigned_at`, `picked_up_at` (and other lifecycle timestamps as implemented), `delivered_at`, completion `latitude`/`longitude` when provided, and `delivery_duration` (or duration seconds) when start and end timestamps exist. Meal fulfillment `status` (`scheduled` / `delivered` / `skipped` / `missed`) MUST remain the source of truth for wallet and skip/miss rules.

#### Scenario: Mark delivered persists rider attribution and delivered time
- **WHEN** a verified Delivery Man successfully marks a scheduled stop as meal `delivered`
- **THEN** the system stores the rider attribution, sets `delivered_at` (or equivalent), and retains meal status `delivered`

#### Scenario: Completion GPS stored when provided
- **WHEN** a Delivery Man mark request includes valid latitude and longitude
- **THEN** the system stores those coordinates on the stop’s completion audit fields

#### Scenario: Mark without GPS still succeeds
- **WHEN** a Delivery Man marks delivered without coordinates (legacy client)
- **THEN** the mark succeeds and GPS fields remain null

### Requirement: Logistics status lifecycle with timestamps
The system SHALL support a logistics status lifecycle for a stop: `assigned` → `accepted` → `picked_up` → `out_for_delivery` → `delivered`, with terminal `failed` or `cancelled` where product rules allow. Each transition MUST record a timestamp for that status. Illegal transitions MUST be rejected with `409` or `422` without corrupting prior timestamps.

#### Scenario: Picked up records timestamp
- **WHEN** an authorized actor transitions a stop to logistics status `picked_up`
- **THEN** the system sets logistics status to `picked_up` and records `picked_up_at`

#### Scenario: Invalid transition rejected
- **WHEN** an actor attempts to move a stop from `assigned` directly to `delivered` without required intermediate steps **if** intermediate steps are enforced for that client path
- **THEN** the system rejects the transition with a client error and leaves prior logistics state unchanged

#### Scenario: Phase A deliver shortcut
- **WHEN** Phase A mobile mark-delivered is used and intermediate logistics steps were not recorded
- **THEN** the system MAY set logistics status to `delivered` and `delivered_at` while leaving earlier lifecycle timestamps null

### Requirement: Delivery activity log records each status event
The system SHALL append a `DeliveryActivityLog` (or equivalent) row for each logistics status transition, including `delivery` reference, `delivery_man` reference when known, `status`, `timestamp`, and optional `latitude`/`longitude`. Timeline APIs MUST read from this log (or a documented equivalent event source), not infer events solely from `OrderDelivery.updated_at`.

#### Scenario: Delivered event appears in activity log
- **WHEN** a stop is marked logistics or meal delivered with attribution
- **THEN** an activity log entry exists with status `delivered` and a timestamp

### Requirement: Delivery man daily summary supports fast dashboards
The system SHALL maintain a per-rider per-calendar-date summary including at least `total_delivery`, `lunch_count`, `dinner_count`, `completed_count`, `failed_count`, and `average_time` (or equivalent fields). Summaries MUST be updated when counted transitions occur (or via an idempotent rebuild). Admin today/month/lifetime KPI endpoints MUST prefer summaries or indexed aggregates rather than unbounded full-table scans.

#### Scenario: Completed dinner increments daily summary
- **WHEN** a rider completes a dinner delivery on a given service date
- **THEN** that rider’s daily summary for that date increments dinner and total completed counts

### Requirement: Duration computed from logistics timestamps
When both a documented start timestamp (`picked_up_at`, else `out_for_delivery_at`, else `assigned_at`) and `delivered_at` exist, the system MUST compute and store delivery duration for that stop. When start is missing, duration MAY be null.

#### Scenario: Duration from pick to deliver
- **WHEN** a stop has `picked_up_at` and `delivered_at`
- **THEN** `delivery_duration` equals the positive difference between those timestamps
