## ADDED Requirements

### Requirement: Customer menu responses include package metadata for UI rendering

The system SHALL include a `meta` object on each package entry in `GET /meals/my-package-menu/` responses and on the top-level `GET /meals/order-menu-preview/` response. The `meta` object MUST contain `cycle_days` (integer, days in the target calendar month from the linked `MealCycle`), `total_meals` (integer, expected slot count for the package in that cycle), `meal_period` (`lunch` | `dinner` | `both`), and `meal_period_display` (human-readable label). When no cycle exists for the target month, `cycle_days` and `total_meals` MAY be omitted or null while `meal_period` MUST still reflect the meal category. This metadata MUST be present regardless of `schedule_published` so clients can render duration and meal-option labels before menu slots are available.

#### Scenario: Preview response includes meta for published month

- **WHEN** a verified customer requests order-menu preview for a meal and month with a published schedule
- **THEN** the response includes `meta.cycle_days`, `meta.total_meals`, `meta.meal_period`, and `meta.meal_period_display` alongside `days`

#### Scenario: Preview response includes meta when unpublished

- **WHEN** a verified customer requests order-menu preview for a meal and month with no published schedule
- **THEN** the response includes `schedule_published` false, empty `days`, and `meta` with `meal_period` and `cycle_days` when the cycle exists

#### Scenario: Package menu entry includes meta

- **WHEN** a verified customer with an active subscription requests my-package-menu for a month
- **THEN** each item in `packages` includes a `meta` object with the same fields as the order-menu preview endpoint

#### Scenario: Meta does not weaken ownership scoping

- **WHEN** a verified customer requests my-package-menu
- **THEN** adding `meta` does not change which packages or day slots are returned; ownership rules remain unchanged
