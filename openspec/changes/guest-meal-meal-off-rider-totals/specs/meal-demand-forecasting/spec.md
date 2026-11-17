# Spec Delta

## ADDED Requirements

### Requirement: Demand includes countable Guest Meal units without double-counting regular stops

For a given `service_date` and `meal_period`, demand MUST include countable prepaid Guest Meal quantities in expected/final cooking counts without replacing or double-counting the regular `OrderDelivery` row. Regular meal-off and low-balance rules still apply to the regular unit.

#### Scenario: Guest units add to final cooking count

- **WHEN** one live non-skipped delivery exists for `(D, lunch)` and the same customer has `2` countable Guest Meals for that slot
- **THEN** demand for `(D, lunch)` includes the regular unit plus `2` guest units in cooking counts

#### Scenario: Cancelled guest units excluded from demand

- **WHEN** a Guest Meal for `(D, dinner)` is cancelled and no other countable guest units exist for that slot
- **THEN** demand for `(D, dinner)` does not include that cancelled guest quantity
