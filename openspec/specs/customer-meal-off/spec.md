# Customer Meal Off

## Purpose
Allow customers to opt out of scheduled lunch or dinner deliveries before the configured preparation deadline.

## Requirements

### Requirement: Customer can meal-off an owned scheduled delivery

The system SHALL allow a verified customer who owns the order to meal-off a delivery slot that is still `scheduled`. On success the system MUST set the delivery status to `skipped`, record that the skip was customer-initiated, set `marked_at`, and associate the acting user. Meal-off MUST mean no meal is expected for that customer for that `service_date` + `meal_period`.

#### Scenario: Successful lunch meal-off before deadline

- **WHEN** a verified customer meal-offs their scheduled lunch delivery for `2026-07-24` while still before the lunch deadline
- **THEN** the delivery status is `skipped`, `skip_source` is `customer`, and kitchen/ops treat the slot as no meal for that customer

#### Scenario: Successful dinner meal-off before deadline

- **WHEN** a verified customer meal-offs their scheduled dinner delivery for `2026-07-23` while still before the dinner deadline
- **THEN** the delivery status is `skipped` and `skip_source` is `customer`

#### Scenario: Other customer's delivery rejected

- **WHEN** a verified customer attempts to meal-off a delivery belonging to another customer's order
- **THEN** the system rejects the request with `404` or `403` without changing the delivery

#### Scenario: Already terminal delivery rejected

- **WHEN** a customer attempts to meal-off a delivery that is already `delivered`, `skipped`, or `missed`
- **THEN** the system rejects the request with a validation/conflict error

### Requirement: Meal-off enforces period deadlines

The system MUST reject meal-off when the current business time is after the deadline for that slot:

- For `meal_period=lunch` on service date `D`, the deadline is calendar date `D − 1` at the configured lunch off time (default `23:59`).
- For `meal_period=dinner` on service date `D`, the deadline is calendar date `D` at the configured dinner off time (default `14:00`).

Deadline evaluation MUST use the meal-off settings timezone.

#### Scenario: Lunch for the 24th blocked after 23rd 23:59

- **WHEN** business time is `2026-07-24 00:00` (settings timezone) and the customer meal-offs lunch for `2026-07-24`
- **THEN** the system rejects the request because the lunch deadline (`2026-07-23 23:59`) has passed

#### Scenario: Lunch for the 24th allowed on 23rd before 23:59

- **WHEN** business time is `2026-07-23 23:50` and the customer meal-offs lunch for `2026-07-24`
- **THEN** the meal-off succeeds

#### Scenario: Dinner for the 23rd blocked after 14:00

- **WHEN** business time is `2026-07-23 14:01` and the customer meal-offs dinner for `2026-07-23`
- **THEN** the system rejects the request

#### Scenario: Dinner for the 23rd allowed before 14:00

- **WHEN** business time is `2026-07-23 13:59` and the customer meal-offs dinner for `2026-07-23`
- **THEN** the meal-off succeeds

### Requirement: Delivery payloads expose meal-off eligibility

For customer-visible delivery representations on order detail / current package, the system SHALL include whether meal-off is currently allowed and the deadline timestamp for that slot.

#### Scenario: Scheduled lunch shows can_meal_off true before deadline

- **WHEN** a customer retrieves an order detail containing a scheduled lunch whose deadline has not passed
- **THEN** that delivery includes `can_meal_off=true` and a `meal_off_deadline_at` matching the lunch deadline rule

#### Scenario: Past-deadline slot shows can_meal_off false

- **WHEN** a customer retrieves a scheduled dinner whose dinner deadline has already passed
- **THEN** that delivery includes `can_meal_off=false`

### Requirement: Meal-off participates in order completion

When a customer meal-offs a slot, the system MUST treat that slot as terminal for progress. If all expected deliveries for the order are terminal, the system MUST complete the order using the existing lifecycle rules.

#### Scenario: Daily lunch package completes after meal-off

- **WHEN** a daily lunch-only order has its single scheduled slot meal-offed successfully
- **THEN** the order becomes `completed`
