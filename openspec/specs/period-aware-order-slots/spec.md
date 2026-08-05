## Purpose

Order delivery slot generation and completion expectations aligned to the purchased package’s meal period.

## Requirements

### Requirement: Order stores meal period snapshot

When a customer successfully places an order for a meal package, the system MUST persist `meal_period_snapshot` from the package’s `meal_period` at purchase time. Delivery generation and expected counts MUST use the snapshot, not the live package field.

#### Scenario: Snapshot copied on order create

- **WHEN** a customer orders a package with `meal_period=dinner`
- **THEN** the created order stores `meal_period_snapshot` as `dinner`

### Requirement: Delivery slots match meal period and duration

The system SHALL generate delivery slots for each service day in the order period according to `meal_period_snapshot`: `lunch` → lunch only; `dinner` → dinner only; `both` → lunch and dinner. Slot dates MUST follow the same duration windows as today (daily = order start date; monthly = days in `order_month`; other types = inclusive start–end range).

#### Scenario: Daily lunch one slot

- **WHEN** deliveries are generated for a daily order with `meal_period_snapshot=lunch`
- **THEN** exactly one slot exists on the service date with `meal_period=lunch`

#### Scenario: Daily both two slots

- **WHEN** deliveries are generated for a daily order with `meal_period_snapshot=both`
- **THEN** exactly two slots exist on the service date (`lunch` and `dinner`)

#### Scenario: Monthly dinner thirty slots in April

- **WHEN** deliveries are generated for a monthly April order with `meal_period_snapshot=dinner`
- **THEN** exactly `30` dinner slots exist and no lunch slots are created

#### Scenario: Monthly both sixty-two slots in January

- **WHEN** deliveries are generated for a monthly January order with `meal_period_snapshot=both`
- **THEN** exactly `62` slots exist (31 lunch + 31 dinner)

### Requirement: Expected delivery count matches generated slots

`expected_delivery_count` for an order MUST equal `service_days × periods_per_day(meal_period_snapshot)` using the same rules as package expected servings for that order’s duration and month.

#### Scenario: Weekly lunch expected count

- **WHEN** expected delivery count is computed for a weekly order with `meal_period_snapshot=lunch`
- **THEN** the count is `7`

#### Scenario: Weekly both expected count

- **WHEN** expected delivery count is computed for a weekly order with `meal_period_snapshot=both`
- **THEN** the count is `14`
