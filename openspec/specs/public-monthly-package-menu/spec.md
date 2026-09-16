# public-monthly-package-menu Specification

## Purpose
TBD - created by archiving change fix-published-menu-month-visibility. Update Purpose after archive.
## Requirements
### Requirement: Public package menu exposes published-month discovery metadata

The system SHALL include `nearest_published_month` and `published_months` on every successful `200` response from `GET /meals/public-package-menu/` for an active meal package. `nearest_published_month` MUST be an object `{ "year": integer, "month": integer }` or `null` when no published schedule exists for that meal. `published_months` MUST be a sorted list (ascending by year then month) of `{ "year", "month" }` objects for all published schedules linked to the meal's cycle plans. When the requested `(year, month)` has a published schedule, `nearest_published_month` MUST equal that month. When the requested month is unpublished but another month is published, `nearest_published_month` MUST be the published month with the smallest calendar distance from the requested month, preferring a future month on ties. The system MUST NOT change `schedule_published`, `days`, or `meta` semantics for the requested month. Discovery metadata MUST be computed from published schedules only (draft schedules MUST NOT appear).

#### Scenario: Requested month published

- **WHEN** an unauthenticated client requests the public package menu for a meal and month that has a published `MonthlyMenuSchedule`
- **THEN** the response includes `schedule_published` true, `nearest_published_month` equal to the requested year/month, and that month listed in `published_months`

#### Scenario: Requested month unpublished but future month published

- **WHEN** an unauthenticated client requests August 2026 for Student Package and only September 2026 is published
- **THEN** the response includes `schedule_published` false, empty `days`, `nearest_published_month` `{ "year": 2026, "month": 9 }`, and `published_months` containing September 2026

#### Scenario: No published schedules

- **WHEN** an unauthenticated client requests any month for a meal with no published schedules
- **THEN** `nearest_published_month` is `null` and `published_months` is an empty list

#### Scenario: Multiple published months

- **WHEN** a meal has published schedules for July and September 2026 and the client requests August 2026
- **THEN** `published_months` lists both July and September in ascending order and `nearest_published_month` is July or September per the smallest-distance rule with future tie-break

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

