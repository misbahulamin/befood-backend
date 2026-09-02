## MODIFIED Requirements

### Requirement: Kitchen today cooking requirement API

The system SHALL provide a lean Kitchen/Admin endpoint that returns the cooking requirement for a single `(service_date, meal_period)` without admin analytics nesting. By default, when `service_date` and `meal_period` are omitted, the system MUST use today’s date in the meal-off settings timezone and infer meal period from the business clock in that timezone: if local time is strictly before the configured `dinner_off_time`, default `meal_period` is `lunch`; otherwise default `meal_period` is `dinner`. Callers MAY override with explicit `service_date` and `meal_period` query params. Callers MAY also filter with optional `package_public_id`; when provided, demand and ingredient aggregation MUST be scoped to that package only. Response MUST include: service date, meal period, final cooking count (people to cook for), expected count, meal-off count, `total_customers`, `confirmation_status`, package-wise demand rows (`packages`), ingredient quantity list, and `ingredients_incomplete`. Access MUST be limited to verified admins (same gate as the existing kitchen board); customers MUST be denied. Existing lean top-level count fields MUST remain for backward compatibility.

#### Scenario: Morning default is today lunch

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 10:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=lunch` and includes final cooking count, packages, and ingredients

#### Scenario: Afternoon default is today dinner

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 15:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=dinner`

#### Scenario: Explicit override

- **WHEN** a verified admin requests `service_date=2026-08-10` and `meal_period=dinner`
- **THEN** the response is scoped to that date and dinner regardless of current clock

#### Scenario: Package filter scopes kitchen requirement

- **WHEN** a verified admin requests the kitchen today-requirement endpoint with a valid `package_public_id`
- **THEN** `packages` contains only that package and ingredient aggregation uses only that package’s final cooking count and published slot items

#### Scenario: Customer denied kitchen requirement

- **WHEN** a verified customer calls the kitchen today-requirement endpoint
- **THEN** the system denies access with `401` or `403`

## ADDED Requirements

### Requirement: Kitchen ingredient rows expose package contributions

The kitchen today-requirement ingredient list SHALL include, for each aggregated ingredient, `customer_count` (sum of contributing packages’ `final_cooking_count`) and `package_contributions` (per contributing package public id, name, and customer count). Kilogram scaling rules from the existing ingredient quantity requirement MUST remain unchanged. Clients that ignore these additive fields MUST continue to function using existing quantity fields.

#### Scenario: Contribution breakdown for shared ingredient

- **WHEN** Premium final dinner count is `170` and Regular is `250`, and both published slots include Chicken
- **THEN** the Chicken ingredient row includes `customer_count=420` and package contributions for Premium (`170`) and Regular (`250`)

#### Scenario: Additive fields do not remove lean quantity fields

- **WHEN** a kitchen today-requirement response includes ingredients with contribution fields
- **THEN** each ingredient still includes `ingredient_public_id`, `name`, `quantity_available`, and quantity/unit fields as before when applicable
