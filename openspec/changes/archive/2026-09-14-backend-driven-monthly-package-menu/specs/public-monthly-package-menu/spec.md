## ADDED Requirements

### Requirement: Public can read published monthly package menu for marketing pages

The system SHALL provide an unauthenticated endpoint `GET /meals/public-package-menu/` that returns the published monthly lunch and dinner menu for an active meal package identified by `meal_public_id` and an optional calendar `year`/`month` (default: current local month). The response MUST include meal identity (`meal_public_id`, `meal_name`), `schedule_published`, a `meta` object with `cycle_days`, `total_meals`, `meal_period` (`lunch` | `dinner` | `both`), and `meal_period_display`, and an ordered flat `days` list with `service_date`, `meal_period`, and ingredient entries (`id`, `name`, `product_role`). The system MUST apply the same ingredient visibility rules as customer menu endpoints (omit `is_customer_visible=false`; `product_role` from plan lines). The system MUST NOT return draft or unpublished schedule slot contents. The system MUST NOT expose customer, order, subscription, or wallet data. The system MUST NOT apply today-menu reveal-time gating.

#### Scenario: Published menu for active package

- **WHEN** an unauthenticated client requests the public package menu for an active meal with a published `MonthlyMenuSchedule` for the target month
- **THEN** the system responds `200` with `schedule_published` true, populated `meta`, and all published day slots in `days`

#### Scenario: Unpublished month returns empty days

- **WHEN** an unauthenticated client requests the public package menu for a meal and month with no published schedule
- **THEN** the system responds `200` with `schedule_published` false, an empty `days` list, and `meta` reflecting the meal's `meal_period` and the cycle's `cycle_days` when the cycle exists

#### Scenario: Inactive or unknown meal rejected

- **WHEN** a client supplies an unknown `meal_public_id` or a meal that is not active
- **THEN** the system responds `404 Not Found`

#### Scenario: Invalid month query

- **WHEN** a client supplies an invalid `month` (outside 1–12) or only one of `year`/`month`
- **THEN** the system responds `400 Bad Request`

#### Scenario: Missing meal_public_id

- **WHEN** a client omits `meal_public_id`
- **THEN** the system responds `400 Bad Request`

#### Scenario: Meta cycle_days matches calendar month length

- **WHEN** the target month has 31 calendar days and a `MealCycle` exists for that month
- **THEN** `meta.cycle_days` is `31` and clients can display "31 Days Menu"

#### Scenario: Meta meal_period reflects package setting

- **WHEN** the meal package has `meal_period` `lunch`
- **THEN** `meta.meal_period` is `lunch` and `meta.meal_period_display` is a human-readable label for that period
