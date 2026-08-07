## Purpose

Lean kitchen/admin API for today's cooking headcount and ingredient quantities scaled by final cooking count for a service date and meal period.

## Requirements

### Requirement: Kitchen today cooking requirement API

The system SHALL provide a lean Kitchen/Admin endpoint that returns the cooking requirement for a single `(service_date, meal_period)` without admin analytics nesting. By default, when `service_date` and `meal_period` are omitted, the system MUST use today’s date in the meal-off settings timezone and infer meal period from the business clock in that timezone: if local time is strictly before the configured `dinner_off_time`, default `meal_period` is `lunch`; otherwise default `meal_period` is `dinner`. Callers MAY override with explicit `service_date` and `meal_period` query params. Response MUST include: service date, meal period, final cooking count (people to cook for), expected count, meal-off count, `confirmation_status`, and ingredient quantity list. Access MUST be limited to verified admins (same gate as the existing kitchen board); customers MUST be denied.

#### Scenario: Morning default is today lunch

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 10:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=lunch` and includes final cooking count and ingredients

#### Scenario: Afternoon default is today dinner

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 15:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=dinner`

#### Scenario: Explicit override

- **WHEN** a verified admin requests `service_date=2026-08-10` and `meal_period=dinner`
- **THEN** the response is scoped to that date and dinner regardless of current clock

#### Scenario: Customer denied kitchen requirement

- **WHEN** a verified customer calls the kitchen today-requirement endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Ingredient quantities scale with final cooking count

The system SHALL calculate kitchen ingredient requirements for a `(service_date, meal_period)` by resolving the published monthly menu schedule ingredients assigned to that slot for each package that has demand, then aggregating quantities across packages. For each ingredient with a complete kilogram pricing pair (`price_per_kg` and `customers_per_kg`), per-person kilograms MUST be `1 / customers_per_kg`, and total kilograms MUST be `per_person_kg × package_final_cooking_count`, summed across packages that include that ingredient on the slot. Quantities MUST use decimal arithmetic (not binary floats) and MUST be returned with unit `kg` when derived from kg yield. Ingredients present on the slot without resolvable kg yield MUST still appear in the list with quantity `null` (or omitted quantity) and a flag indicating quantity could not be computed, without failing the entire requirement response. Flat `cost_per_customer`-only ingredients MUST NOT invent a kilogram quantity.

#### Scenario: Rice scaled by final count

- **WHEN** dinner final cooking count is `450` for a package whose published dinner slot includes Rice with `customers_per_kg=10/3` (0.3 kg per person) and no other package contributes Rice
- **THEN** the ingredient list includes Rice with total quantity `135` kg (within documented decimal precision)

#### Scenario: Multi-package aggregation

- **WHEN** Premium final dinner count is `170` and Regular is `250`, and both slots include Chicken with the same `customers_per_kg`
- **THEN** Chicken total quantity equals per-person kg × `(170 + 250)`

#### Scenario: Flat-cost spice without kg yield

- **WHEN** a slot ingredient has only flat `cost_per_customer` and no `customers_per_kg`
- **THEN** the kitchen response still lists the ingredient for awareness but does not invent a kg quantity

### Requirement: Missing menu does not invent ingredients

When no published monthly menu schedule assignment exists for a package’s `(service_date, meal_period)`, the system MUST still return cooking headcount for that package/period and MUST return an empty or partial ingredient list for packages lacking menu data, without fabricating ingredients from the cycle plan’s full month matrix alone unless the design explicitly maps slot assignments only. The response MUST indicate when ingredient data is incomplete for the slot.

#### Scenario: Counts without published slot menu

- **WHEN** demand exists for `(D, lunch)` but the package’s monthly menu schedule has no published ingredients for that slot
- **THEN** final cooking count is still returned and the ingredient list is empty or marked incomplete for that package
