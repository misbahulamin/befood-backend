## Purpose

Shared meal demand calculation for a service date and meal period: expected, meal-off, and final cooking counts with package-wise breakdown and confirmation status for admin statistics.

## Requirements

### Requirement: Demand counts derive from order deliveries per date and period

The system SHALL compute meal demand for a given `service_date` and `meal_period` (`lunch` or `dinner`) from non-cancelled order deliveries that match that date and period. **Expected meal count** MUST equal the number of such deliveries whose status is not cancelled-order–excluded (deliveries belonging to orders in cancellable-terminal cancelled state MUST be excluded). **Meal-off count** MUST equal the number of those deliveries with status `skipped`. **Final cooking count** MUST equal `expected_meal_count - meal_off_count`, which MUST also equal the count of deliveries that remain expected for cooking (status in `{scheduled, preparing, out_for_delivery, delivered, missed}` or the project’s equivalent non-skipped, non-cancelled-order delivery set used for kitchen planning). Counts MUST be integers and MUST never be negative.

#### Scenario: Baseline expected equals active slot holders

- **WHEN** 500 non-cancelled orders each have a scheduled dinner delivery on date `D` and none are skipped
- **THEN** expected meal count for `(D, dinner)` is `500`, meal-off count is `0`, and final cooking count is `500`

#### Scenario: Meal-off reduces final cooking count

- **WHEN** 500 expected dinner deliveries exist on date `D` and 50 of them are `skipped`
- **THEN** expected is `500`, meal-off is `50`, and final cooking count is `450`

#### Scenario: Cancelled order deliveries excluded

- **WHEN** a delivery exists for `(D, lunch)` but its parent order is `cancelled`
- **THEN** that delivery is excluded from expected, meal-off, and final cooking counts for `(D, lunch)`

### Requirement: Confirmation status follows meal-off deadline

For each `(service_date, meal_period)` demand result, the system SHALL set `confirmation_status` to `estimated` while business time (meal-off settings timezone) is at or before that slot’s meal-off deadline, and to `confirmed` after the deadline has passed. Deadline rules MUST reuse existing meal-off settings (lunch: prior calendar day at lunch off time; dinner: service date at dinner off time). Admin and kitchen responses MUST expose `confirmation_status` so clients can distinguish provisional vs locked cooking numbers. After confirmation, live recalculation MUST still reflect any admin-driven skips that remain allowed by other flows, but customer meal-off/meal-on MUST already be blocked by existing deadline rules.

#### Scenario: Before dinner deadline status is estimated

- **WHEN** business time on date `D` is before the configured dinner off time and demand for `(D, dinner)` is requested
- **THEN** the response includes `confirmation_status=estimated` and final cooking count equals expected minus current meal-offs

#### Scenario: After dinner deadline status is confirmed

- **WHEN** business time on date `D` is after the configured dinner off time and demand for `(D, dinner)` is requested
- **THEN** the response includes `confirmation_status=confirmed`

#### Scenario: Lunch for tomorrow estimated on prior evening

- **WHEN** business time is on `D−1` before the lunch off time and demand for lunch on `D` is requested
- **THEN** `confirmation_status` is `estimated`

### Requirement: Package-wise demand isolation

The system SHALL compute and return demand metrics grouped by meal package (`MealCategory` / ordered meal) in addition to overall totals for a date and period. Each package row MUST include package identity (public id and name), total customer/order count contributing deliveries for that slot, expected meal count, meal-off count, and final cooking count. Overall totals MUST equal the sum of package-wise expected, meal-off, and final counts for the same date and period. Package grouping MUST use the ordered meal/package on the delivery’s parent order so packages remain isolated.

#### Scenario: Premium and regular breakdown

- **WHEN** Premium has 200 expected dinners with 30 offs and Regular has 300 expected dinners with 50 offs on date `D`
- **THEN** package-wise final counts are `170` and `250` respectively and overall final cooking count is `420`

#### Scenario: Filter by package returns only that package

- **WHEN** a verified admin requests demand for date `D`, period `dinner`, filtered to Premium’s public id
- **THEN** the response includes only Premium package metrics and overall totals match that package

### Requirement: Admin meal statistics API

The system SHALL provide a verified-admin (web) meal statistics endpoint that accepts filters for `service_date` (required or defaulting to today in meal-off timezone), optional `meal_period` (`lunch` | `dinner` | omit for both), and optional package public id. The response MUST include overall metrics: total contributing customers/orders, expected total meal, total meal off, final cooking requirement, and remaining/active expected meals consistent with final cooking semantics, plus package-wise breakdown and `confirmation_status` per period returned. When both periods are requested, lunch and dinner MUST be returned as separate period blocks. Non-admin callers MUST receive `401` or `403`.

#### Scenario: Admin views dinner statistics for a date

- **WHEN** a verified admin requests statistics for `service_date=D` and `meal_period=dinner`
- **THEN** the response includes overall expected, meal-off, final cooking, package-wise rows, and `confirmation_status` for dinner on `D`

#### Scenario: Date with lunch and dinner without period filter

- **WHEN** a verified admin requests statistics for `service_date=D` without `meal_period`
- **THEN** the response includes separate lunch and dinner demand blocks for `D`

#### Scenario: Customer denied statistics

- **WHEN** a verified customer calls the meal statistics endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Deterministic single calculation path

The system MUST compute expected, meal-off, and final cooking counts through one shared domain service used by admin statistics, kitchen requirement, and history snapshot writers. Duplicate divergent formulas across endpoints MUST NOT exist. Live reads MUST derive from current delivery rows unless a confirmed historical snapshot is explicitly requested via the history capability.

#### Scenario: Admin and kitchen agree on same slot

- **WHEN** admin statistics and kitchen requirement both resolve demand for the same `(D, dinner)` at the same moment
- **THEN** both report identical expected, meal-off, final cooking counts and the same `confirmation_status`
