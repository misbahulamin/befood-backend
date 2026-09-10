## ADDED Requirements

### Requirement: Kitchen cooking counts are live until slot meal-off cutoff

The system SHALL compute `GET /orders/kitchen/today-meal-requirement/` and `GET /orders/kitchen/today-order-details/` (and their `/api/v1/web/...` aliases) from the current `OrderDelivery` population for the requested `(service_date, meal_period)` while the slot’s meal-off deadline has not passed. The system MUST NOT serve a day-start frozen snapshot for these live kitchen endpoints before that deadline. Response `confirmation_status` MUST remain `estimated` before the deadline and `confirmed` after, consistent with meal-off settings timezone clocks.

#### Scenario: Pre-cutoff refresh reflects new cook-eligible delivery

- **WHEN** a verified admin requests today-meal-requirement for lunch before the lunch meal-off deadline and a new cook-eligible (`scheduled`) delivery for that lunch slot becomes live (for example via subscription ensure before cutoff)
- **THEN** a subsequent GET returns a higher `final_cooking_count` (and order-details `count` increases when the row is not skipped) without requiring a deploy or cache flush

#### Scenario: Skipped late slot does not increase final cooking

- **WHEN** a customer subscribes after the lunch meal-off deadline and `ensure_subscription_deliveries` creates today’s lunch as `skipped` with cutoff eligibility
- **THEN** `final_cooking_count` and order-details `count` MUST NOT increase for that lunch slot solely due to that skipped row (while `expected_meal_count` / `total_customers` MAY still include the skipped delivery per existing aggregate rules)

### Requirement: Kitchen default period switch must not be mistaken for same-slot drift

When `service_date` and `meal_period` query parameters are both omitted, the system MUST continue to default `service_date` to today in the meal-off settings timezone and default `meal_period` to `lunch` if local time is strictly before `dinner_off_time`, otherwise `dinner`. Clients that need a stable cook list for a specific slot MUST pass explicit `service_date` and `meal_period`. The response MUST echo the resolved `service_date` and `meal_period` so operators can detect an unintended period switch.

#### Scenario: Explicit period stays stable across dinner_off_time

- **WHEN** a verified admin calls today-meal-requirement with `meal_period=lunch` and today’s `service_date` both before and after `dinner_off_time`
- **THEN** both responses use `meal_period=lunch` (counts may still change only due to live eligibility mutations, not due to default period inference)

### Requirement: Post-cutoff kitchen freeze (target behavior for follow-up implementation)

After the meal-off deadline for a `(service_date, meal_period)` has passed, the kitchen today-meal-requirement and today-order-details endpoints MUST present a stable cook headcount for that slot such that newly becoming cook-eligible after the deadline (late create-as-scheduled if ever allowed, post-cutoff low-balance resume, or equivalent) MUST NOT increase kitchen `final_cooking_count` or order-details `count` for that slot. Existing `OrderDelivery` rows MUST NOT be deleted to achieve stability. Wallet charging / auto-delivery behavior MUST remain unchanged unless a separate approved change explicitly aligns those paths with the freeze.

#### Scenario: Post-cutoff resume does not grow kitchen cook list

- **WHEN** the lunch meal-off deadline has passed and a previously low-balance-blocked customer is resumed with a still-`scheduled` lunch delivery
- **THEN** kitchen today-meal-requirement `final_cooking_count` and today-order-details `count` for that lunch slot MUST NOT increase solely because of that resume (follow-up implementation)

#### Scenario: Historical deliveries preserved

- **WHEN** the post-cutoff freeze is applied
- **THEN** no `OrderDelivery` rows are deleted or status-rewritten solely to stabilize kitchen counts
