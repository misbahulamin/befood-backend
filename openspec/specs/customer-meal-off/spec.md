# Customer Meal Off

## Purpose
Allow customers to opt out of scheduled lunch or dinner deliveries before the configured preparation deadline, and to turn those meals back on while the same deadline has not yet passed.

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

For customer-visible delivery representations on order detail / current package, the system SHALL include whether meal-off is currently allowed and the deadline timestamp for that slot. After the deadline, `can_meal_off` MUST be false even if the delivery is still `scheduled`.

#### Scenario: Scheduled lunch shows can_meal_off true before deadline

- **WHEN** a customer retrieves an order detail containing a scheduled lunch whose deadline has not passed
- **THEN** that delivery includes `can_meal_off=true` and a `meal_off_deadline_at` matching the lunch deadline rule

#### Scenario: Past-deadline slot shows can_meal_off false

- **WHEN** a customer retrieves a scheduled dinner whose dinner deadline has already passed
- **THEN** that delivery includes `can_meal_off=false`

#### Scenario: Customer-skipped slot shows can_meal_off false

- **WHEN** a delivery is already customer-skipped
- **THEN** that delivery includes `can_meal_off=false`

### Requirement: Meal-off participates in order completion

When a customer meal-offs a slot, the system MUST treat that slot as terminal for progress. If all expected deliveries for the order are terminal, the system MUST complete the order using the existing lifecycle rules.

#### Scenario: Daily lunch package completes after meal-off

- **WHEN** a daily lunch-only order has its single scheduled slot meal-offed successfully
- **THEN** the order becomes `completed`

### Requirement: Customer can meal-on a customer-skipped delivery before deadline

The system SHALL allow a verified customer who owns the order to meal-on (undo meal-off) a delivery that is `skipped` with `skip_source=customer`, while business time is still at or before that slot’s meal-off deadline. On success the system MUST set the delivery status back to `scheduled`, clear customer skip markers (`skip_source` and related mark fields used for the skip), and treat the slot again as an expected meal for that `service_date` + `meal_period`. Meal-on MUST NOT debit the wallet.

#### Scenario: Successful dinner meal-on before deadline

- **WHEN** a verified customer has meal-offed dinner for service date `D` (status `skipped`, `skip_source=customer`) and business time is still before the dinner deadline on `D`
- **THEN** meal-on succeeds, the delivery status is `scheduled`, and no wallet debit is created for that action

#### Scenario: Lunch meal-on blocked after deadline

- **WHEN** a customer meal-offed lunch for service date `D` before the lunch deadline, and later business time is after the lunch deadline for `D`
- **THEN** meal-on is rejected and the delivery remains `skipped`

#### Scenario: Admin-skipped delivery cannot be meal-oned by customer

- **WHEN** a delivery is `skipped` with `skip_source=admin` and the customer requests meal-on before the deadline
- **THEN** the system rejects the request without changing the delivery

#### Scenario: Other customer's delivery rejected for meal-on

- **WHEN** a verified customer attempts to meal-on a delivery belonging to another customer's order
- **THEN** the system rejects the request with `404` or `403` without changing the delivery

### Requirement: Deadline locks both meal-off and meal-on

The system MUST reject meal-off and meal-on when business time is after the deadline for that slot. When rejected for deadline, the system MUST leave the delivery status and skip markers unchanged. Deadline evaluation MUST use the same rules and timezone as meal-off settings:

- For `meal_period=lunch` on service date `D`, the deadline is calendar date `D − 1` at the configured lunch off time.
- For `meal_period=dinner` on service date `D`, the deadline is calendar date `D` at the configured dinner off time.

#### Scenario: After dinner deadline neither off nor on is allowed

- **WHEN** business time on service date `D` is after the configured dinner off time and the dinner delivery for `D` is still `scheduled`
- **THEN** meal-off is rejected and the delivery remains `scheduled`

#### Scenario: After dinner deadline meal-on of prior off is rejected

- **WHEN** dinner for `D` was meal-offed earlier and business time on `D` is after the dinner off time
- **THEN** meal-on is rejected and the delivery remains `skipped`

#### Scenario: Before dinner deadline customer may toggle off then on

- **WHEN** business time on `D` is still before the dinner off time
- **THEN** the customer may meal-off dinner for `D` and later meal-on the same delivery successfully

### Requirement: Delivery payloads expose meal-on eligibility

For customer-visible delivery representations on order detail / current package, the system SHALL include whether meal-on is currently allowed. Meal-on eligibility MUST be true only when the delivery is customer-skipped, the order is not cancelled, and the slot deadline has not passed.

#### Scenario: Customer-skipped dinner shows can_meal_on true before deadline

- **WHEN** a customer retrieves an order detail containing a customer-skipped dinner whose deadline has not passed
- **THEN** that delivery includes `can_meal_on=true`

#### Scenario: Past-deadline skipped slot shows can_meal_on false

- **WHEN** a customer retrieves a customer-skipped lunch whose lunch deadline has already passed
- **THEN** that delivery includes `can_meal_on=false`

#### Scenario: Scheduled slot shows can_meal_on false

- **WHEN** a delivery is still `scheduled`
- **THEN** that delivery includes `can_meal_on=false`

### Requirement: Meal-on reopens an order completed by meal-off

When meal-on restores a delivery to `scheduled` and the parent order is `completed` only because all slots had become terminal, the system MUST reopen the order to a non-terminal status (`active`, or `confirmed` when no deliveries have been `delivered` yet) so the slot can still progress through normal delivery lifecycle.

#### Scenario: Daily lunch package reopens after meal-on

- **WHEN** a daily lunch-only order was completed after its only slot was meal-offed, and the customer meal-ons that slot before the lunch deadline
- **THEN** the delivery is `scheduled` and the order is no longer `completed`

### Requirement: Default on means delivery and billing apply; off means neither

The system MUST treat a delivery that was never meal-offed (status remains `scheduled` until marked) as meal-on by default: kitchen/ops MAY deliver it and wallet debit rules for `delivered` apply. When a delivery is customer meal-offed (`skipped`), the system MUST NOT expect a meal delivery for that customer for that slot and MUST NOT debit the wallet for that slot while it remains `skipped`.

#### Scenario: Never meal-offed slot remains deliverable

- **WHEN** a customer takes no meal-off action for a scheduled lunch slot and an operator later marks it `delivered` with a sufficient wallet
- **THEN** the meal is treated as accepted and wallet debit rules for delivered meals apply

#### Scenario: Meal-offed slot is not charged while skipped

- **WHEN** a customer successfully meal-offs a scheduled delivery
- **THEN** the delivery is `skipped` and the system does not debit the wallet for that slot
