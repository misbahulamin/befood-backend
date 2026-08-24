## MODIFIED Requirements

### Requirement: Demand counts derive from order deliveries per date and period

The system SHALL compute meal demand for a given `service_date` and `meal_period` (`lunch` or `dinner`) from deliveries that belong to an **active subscription** (or a historical non-cancelled order not yet migrated). **Expected meal count** MUST equal the number of such deliveries that are not excluded because the parent subscription is `cancelled` with `service_date` after `cancel_effective_on`, or because a historical parent order is `cancelled`. **Meal-off count** MUST equal the number of those deliveries with status `skipped`. **Final cooking count** MUST equal `expected_meal_count - meal_off_count`. Counts MUST be integers and MUST never be negative.

#### Scenario: Baseline expected equals active slot holders

- **WHEN** 500 active subscriptions each have a scheduled dinner delivery on date `D` and none are skipped
- **THEN** expected meal count for `(D, dinner)` is `500`, meal-off count is `0`, and final cooking count is `500`

#### Scenario: Meal-off reduces final cooking count

- **WHEN** 500 expected dinner deliveries exist on date `D` and 50 of them are `skipped`
- **THEN** expected is `500`, meal-off is `50`, and final cooking count is `450`

#### Scenario: Cancelled order deliveries excluded

- **WHEN** a delivery exists for `(D, lunch)` but its parent subscription is `cancelled` and `D` is after `cancel_effective_on` (or a historical parent order is `cancelled`)
- **THEN** that delivery is excluded from expected, meal-off, and final cooking counts for `(D, lunch)`

### Requirement: Package-wise demand isolation

The system SHALL compute and return demand metrics grouped by meal package (`MealCategory` / subscribed plan) in addition to overall totals for a date and period. Each package row MUST include package identity (public id and name), total contributing customer/subscription count, expected meal count, meal-off count, and final cooking count. Overall totals MUST equal the sum of package-wise expected, meal-off, and final counts for the same date and period. Package grouping MUST use the meal/package on the delivery’s parent subscription (or historical order) so packages remain isolated.

#### Scenario: Premium and regular breakdown

- **WHEN** Premium has 200 expected dinners with 30 offs and Regular has 300 expected dinners with 50 offs on date `D`
- **THEN** package-wise final counts are `170` and `250` respectively and overall final cooking count is `420`

#### Scenario: Filter by package returns only that package

- **WHEN** a verified admin requests demand for date `D`, period `dinner`, filtered to Premium’s public id
- **THEN** the response includes only Premium package metrics and overall totals match that package

### Requirement: Admin meal statistics API

The system SHALL provide a verified-admin (web) meal statistics endpoint that accepts filters for `service_date` (required or defaulting to today in meal-off timezone), optional `meal_period` (`lunch` | `dinner` | omit for both), and optional package public id. The response MUST include overall metrics: total contributing customers/subscriptions, expected total meal, total meal off, final cooking requirement, and remaining/active expected meals consistent with final cooking semantics, plus package-wise breakdown and `confirmation_status` per period returned. When both periods are requested, lunch and dinner MUST be returned as separate period blocks. Non-admin callers MUST receive `401` or `403`.

#### Scenario: Admin views dinner statistics for a date

- **WHEN** a verified admin requests statistics for `service_date=D` and `meal_period=dinner`
- **THEN** the response includes overall expected, meal-off, final cooking, package-wise rows, and `confirmation_status` for dinner on `D`

#### Scenario: Date with lunch and dinner without period filter

- **WHEN** a verified admin requests statistics for `service_date=D` without `meal_period`
- **THEN** the response includes separate lunch and dinner demand blocks for `D`

#### Scenario: Customer denied statistics

- **WHEN** a verified customer calls the meal statistics endpoint
- **THEN** the system denies access with `401` or `403`
