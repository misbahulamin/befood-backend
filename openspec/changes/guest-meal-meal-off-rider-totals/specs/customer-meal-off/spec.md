# Spec Delta

## ADDED Requirements

### Requirement: Meal-OFF blocked when countable Guest Meal exists for the slot

The system MUST reject customer Meal-OFF for a delivery slot when one or more countable Guest Meals (scheduled status) exist for the same customer, `service_date`, and `meal_period`. The rejection MUST leave the delivery scheduled, MUST NOT cancel or refund Guest Meals, and MUST surface a clear domain error so clients can explain that Guest Meals must be resolved before turning the regular meal OFF. `can_meal_off` for that slot MUST be false while such Guest Meals exist.

#### Scenario: Meal-OFF rejected when guest lunch exists

- **WHEN** a customer has a scheduled Guest Lunch for date `D` and attempts Meal-OFF on the lunch delivery for `D`
- **THEN** the system rejects Meal-OFF, the lunch delivery remains scheduled, and the Guest Meal remains unchanged

#### Scenario: Dinner Meal-OFF still allowed when only lunch guest exists

- **WHEN** a customer has a scheduled Guest Lunch for date `D` and no Guest Dinner for `D`
- **THEN** Meal-OFF for dinner on `D` is still allowed with respect to this Guest Meal rule

#### Scenario: can_meal_off false while guest exists

- **WHEN** a scheduled lunch delivery has at least one scheduled Guest Meal for the same slot and the meal-off deadline has not passed
- **THEN** customer-visible `can_meal_off` for that lunch delivery is false
