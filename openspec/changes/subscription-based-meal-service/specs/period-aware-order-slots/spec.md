## MODIFIED Requirements

### Requirement: Order stores meal period snapshot

When a customer successfully **subscribes** to a meal package, the system MUST persist `meal_period_snapshot` on the `CustomerSubscription` from the plan’s `meal_period` at subscribe time. Delivery generation and expected counts MUST use the snapshot, not the live package field. Historical orders keep their existing `meal_period_snapshot`.

#### Scenario: Snapshot copied on order create

- **WHEN** a customer subscribes to a package with `meal_period=dinner`
- **THEN** the created subscription stores `meal_period_snapshot` as `dinner`

### Requirement: Delivery slots match meal period and duration

The system SHALL generate delivery slots for each service day in the **subscription rolling horizon** according to `meal_period_snapshot`: `lunch` → lunch only; `dinner` → dinner only; `both` → lunch and dinner. Slot dates MUST follow published months inside the horizon, not a closed `order_month` purchase window.

#### Scenario: Daily lunch one slot

- **WHEN** a historical daily order with `meal_period_snapshot=lunch` still has generated deliveries
- **THEN** exactly one slot exists on that order’s service date with `meal_period=lunch`

#### Scenario: Daily both two slots

- **WHEN** a historical daily order with `meal_period_snapshot=both` still has generated deliveries
- **THEN** exactly two slots exist on that service date (`lunch` and `dinner`)

#### Scenario: Monthly dinner thirty slots in April

- **WHEN** deliveries are generated for an active dinner-only subscription covering a published April
- **THEN** exactly `30` dinner slots exist for April and no lunch slots are created for those dates

#### Scenario: Monthly both sixty-two slots in January

- **WHEN** deliveries are generated for an active `both` subscription covering a published January
- **THEN** exactly `62` slots exist for January (31 lunch + 31 dinner) and the subscription remains active afterward

### Requirement: Expected delivery count matches generated slots

`expected_delivery_count` for an active subscription MUST equal the number of generated slots in the current horizon (service days with published menus × periods per day from `meal_period_snapshot`). It MUST NOT imply the subscription will complete when that count is reached.

#### Scenario: Weekly lunch expected count

- **WHEN** expected delivery count is computed for a historical weekly order with `meal_period_snapshot=lunch`
- **THEN** the historical order count remains `7`

#### Scenario: Weekly both expected count

- **WHEN** expected delivery count is computed for a historical weekly order with `meal_period_snapshot=both`
- **THEN** the historical order count remains `14`
