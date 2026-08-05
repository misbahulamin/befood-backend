## Purpose

Admin-selected lunch, dinner, or both meal periods on packages, with a shared serving-count formula across planning, pricing, and APIs.

## Requirements

### Requirement: Admin sets meal period when creating or updating a package

The system SHALL require a `meal_period` on meal package create and update with allowed values `lunch`, `dinner`, or `both`. The system MUST persist `meal_period` on `MealCategory` and MUST include it on admin meal list, detail, create, and update responses. Existing packages without a stored value MUST be treated as `both` after migration.

#### Scenario: Create daily lunch package

- **WHEN** a verified admin creates a meal package with `meal_type=daily` and `meal_period=lunch`
- **THEN** the system stores the package and returns `meal_period` as `lunch`

#### Scenario: Create monthly both package

- **WHEN** a verified admin creates a meal package with `meal_type=monthly` and `meal_period=both`
- **THEN** the system stores the package and returns `meal_period` as `both`

#### Scenario: Missing meal period rejected

- **WHEN** a verified admin creates or updates a meal package without `meal_period`
- **THEN** the system rejects the request with a validation error on `meal_period`

#### Scenario: Invalid meal period rejected

- **WHEN** a verified admin submits `meal_period` with a value other than `lunch`, `dinner`, or `both`
- **THEN** the system rejects the request with a validation error

### Requirement: Expected servings from meal type and meal period

The system SHALL compute expected servings as `service_days(meal_type, year, month) × periods_per_day(meal_period)`, where `periods_per_day` is `1` for `lunch` or `dinner` and `2` for `both`. Service days MUST follow existing duration rules: daily → 1; weekly → 7; half_monthly → 15; monthly → calendar days in the given month; longer types → inclusive day count from that month’s start per order-duration rules.

#### Scenario: Daily lunch is one serving

- **WHEN** expected servings are computed for `meal_type=daily`, `meal_period=lunch`, any year/month
- **THEN** the result is `1`

#### Scenario: Daily both is two servings

- **WHEN** expected servings are computed for `meal_type=daily`, `meal_period=both`
- **THEN** the result is `2`

#### Scenario: Monthly dinner uses calendar days

- **WHEN** expected servings are computed for `meal_type=monthly`, `meal_period=dinner`, year `2026`, month `4`
- **THEN** the result is `30`

#### Scenario: Monthly both doubles calendar days

- **WHEN** expected servings are computed for `meal_type=monthly`, `meal_period=both`, year `2026`, month `1`
- **THEN** the result is `62`

#### Scenario: February monthly both in a leap year

- **WHEN** expected servings are computed for `meal_type=monthly`, `meal_period=both`, year `2028`, month `2`
- **THEN** the result is `58`

### Requirement: Public per-meal price uses package expected servings

When a package has a published `total_price`, the system MUST compute `per_meal_price` as `total_price / expected_servings(meal_type, meal_period, present year, present month)` using decimal money quantization. The system MUST NOT hardcode a divisor of `present_month_days × 2` for every package.

#### Scenario: Monthly dinner per-meal price in April

- **WHEN** a monthly dinner package has `total_price` `3000` and the present month has `30` days
- **THEN** `per_meal_price` equals `3000 / 30` quantized to money precision

#### Scenario: Daily both per-meal price

- **WHEN** a daily both package has `total_price` `200`
- **THEN** `per_meal_price` equals `200 / 2` quantized to money precision
