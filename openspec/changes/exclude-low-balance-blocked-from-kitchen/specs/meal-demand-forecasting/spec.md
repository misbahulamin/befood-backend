## ADDED Requirements

### Requirement: Demand excludes low-balance meal-stop blocked customers

The system SHALL exclude any live order delivery from meal-demand calculation when the delivery’s customer has `CustomerProfile.meal_service_blocked_low_balance` equal to `true`. Exclusion MUST apply whether the customer is reached via the subscription parent or the one-shot order parent (same OR semantics as auto meal delivery eligibility). Excluded deliveries MUST NOT contribute to `expected_meal_count`, `meal_off_count`, `final_cooking_count`, or distinct customer totals at overall or package level. Customers with the flag `false` (or unset/default false) MUST remain included subject to existing live-delivery and cancellation rules. Meal-off (`skipped`) status alone MUST NOT be used as a substitute for this exclusion: a blocked customer whose delivery is still meal-on MUST still be omitted from demand.

#### Scenario: Blocked meal-on customer omitted from all counts

- **WHEN** three live dinner deliveries exist on date `D`, one customer has `meal_service_blocked_low_balance=true` with status `scheduled`, and the other two are unblocked and not skipped
- **THEN** expected meal count is `2`, meal-off count is `0`, final cooking count is `2`, and the blocked customer is not counted in `total_customers`

#### Scenario: Blocked customer with meal-off also omitted

- **WHEN** a live delivery on `(D, lunch)` is `skipped` and that customer has `meal_service_blocked_low_balance=true`
- **THEN** that delivery contributes neither to expected nor to meal-off counts for `(D, lunch)`

#### Scenario: Unblocked customers unchanged

- **WHEN** all customers for a slot have `meal_service_blocked_low_balance=false`
- **THEN** demand counts match the existing live-delivery and meal-off rules with no additional omissions

#### Scenario: Admin statistics and kitchen share exclusion

- **WHEN** admin meal statistics and kitchen today-requirement both resolve demand for the same `(D, dinner)` at the same moment and some customers are low-balance blocked
- **THEN** both report identical expected, meal-off, final cooking counts after applying the same block exclusion
