# Spec Delta

## ADDED Requirements

### Requirement: Demand includes countable Test Meal units

Shared meal-demand for a `(service_date, meal_period)` MUST include countable Test Meal units by package in addition to subscription deliveries and Guest Meal quantities, without double-counting. Cancelled or non-cooking Test Meals MUST be excluded.

#### Scenario: Test Meal increases final cooking

- **WHEN** subscription final cooking for `(D, lunch)` is `40`, guest boxes add `3`, and two confirmed Test Meals exist for the same slot
- **THEN** consolidated cooking demand for that slot includes those two Test Meal units without removing the subscription or guest contributions

#### Scenario: Cancelled Test Meal excluded

- **WHEN** a Test Meal for `(D, dinner)` is cancelled
- **THEN** demand for `(D, dinner)` excludes that Test Meal unit

#### Scenario: Admin and kitchen agree including Test Meals

- **WHEN** admin statistics and kitchen requirement both resolve demand for the same slot with Test Meals present
- **THEN** both report identical totals after applying the same Test Meal counting rules
