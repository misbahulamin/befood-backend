## MODIFIED Requirements

### Requirement: Kitchen today cooking requirement API

The system SHALL provide a lean Kitchen/Admin endpoint that returns the cooking requirement for a single `(service_date, meal_period)` without admin analytics nesting. By default, when `service_date` and `meal_period` are omitted, the system MUST use today’s date in the meal-off settings timezone and infer meal period from the business clock in that timezone: if local time is strictly before the configured `dinner_off_time`, default `meal_period` is `lunch`; otherwise default `meal_period` is `dinner`. Callers MAY override with explicit `service_date` and `meal_period` query params. Response MUST include: service date, meal period, final cooking count (people to cook for), expected count, meal-off count, `confirmation_status`, and ingredient quantity list. Access MUST be limited to verified admins (same gate as the existing kitchen board); customers MUST be denied. The endpoint MUST recalculate from live `OrderDelivery` eligibility on each request (it MUST NOT return a day-start HTTP/Redis cached payload). Callers comparing totals across the day MUST use the same explicit `service_date` and `meal_period` to avoid attributing default period switches to count drift.

#### Scenario: Morning default is today lunch

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 10:00 Asia/Dhaka with no query params
- **THEN** the response uses today’s date and `meal_period=lunch` and includes final cooking count and ingredients

#### Scenario: Afternoon default is today dinner

- **WHEN** a verified admin calls the kitchen today-requirement endpoint at 15:00 Asia/Dhaka with no query params and `dinner_off_time` is 14:00 or earlier that day (or otherwise local time is not strictly before `dinner_off_time`)
- **THEN** the response uses today’s date and `meal_period=dinner`

#### Scenario: Explicit override

- **WHEN** a verified admin requests `service_date=2026-08-10` and `meal_period=dinner`
- **THEN** the response is scoped to that date and dinner regardless of current clock

#### Scenario: Customer denied kitchen requirement

- **WHEN** a verified customer calls the kitchen today-requirement endpoint
- **THEN** the system denies access with `401` or `403`

#### Scenario: Live recalculation without response cache

- **WHEN** a verified admin calls kitchen today-requirement twice for the same explicit `(service_date, meal_period)` and cook-eligible deliveries changed between calls
- **THEN** the second response reflects the updated live counts without requiring cache invalidation
