## MODIFIED Requirements

### Requirement: Customer can meal-off an owned scheduled delivery

The system SHALL allow a verified customer who owns the **subscription** (or a historical order still linked to remaining slots) to meal-off a delivery slot that is still `scheduled`. On success the system MUST set the delivery status to `skipped`, record that the skip was customer-initiated, set `marked_at`, and associate the acting user. Meal-off MUST mean no meal is expected for that customer for that `service_date` + `meal_period`.

#### Scenario: Successful lunch meal-off before deadline

- **WHEN** a verified customer meal-offs their scheduled lunch delivery for `2026-07-24` while still before the lunch deadline
- **THEN** the delivery status is `skipped`, `skip_source` is `customer`, and kitchen/ops treat the slot as no meal for that customer

#### Scenario: Successful dinner meal-off before deadline

- **WHEN** a verified customer meal-offs their scheduled dinner delivery for `2026-07-23` while still before the dinner deadline
- **THEN** the delivery status is `skipped` and `skip_source` is `customer`

#### Scenario: Other customer's delivery rejected

- **WHEN** a verified customer attempts to meal-off a delivery belonging to another customer's subscription
- **THEN** the system rejects the request with `404` or `403` without changing the delivery

#### Scenario: Already terminal delivery rejected

- **WHEN** a customer attempts to meal-off a delivery that is already `delivered`, `skipped`, or `missed`
- **THEN** the system rejects the request with a validation/conflict error

### Requirement: Delivery payloads expose meal-off eligibility

For customer-visible delivery representations on subscription detail / current subscription, the system SHALL include whether meal-off is currently allowed and the deadline timestamp for that slot. After the deadline, `can_meal_off` MUST be false even if the delivery is still `scheduled`.

#### Scenario: Scheduled lunch shows can_meal_off true before deadline

- **WHEN** a customer retrieves a subscription detail containing a scheduled lunch whose deadline has not passed
- **THEN** that delivery includes `can_meal_off=true` and a `meal_off_deadline_at` matching the lunch deadline rule

#### Scenario: Past-deadline slot shows can_meal_off false

- **WHEN** a customer retrieves a scheduled dinner whose dinner deadline has already passed
- **THEN** that delivery includes `can_meal_off=false`

#### Scenario: Customer-skipped slot shows can_meal_off false

- **WHEN** a delivery is already customer-skipped
- **THEN** that delivery includes `can_meal_off=false`

## REMOVED Requirements

### Requirement: Meal-off participates in order completion

**Reason:** An active subscription must not complete when slots are meal-offed. Completing the entitlement was a monthly-order lifecycle rule.
**Migration:** Meal-off still marks the slot `skipped` for demand and billing. Subscription status changes only via cancel (or admin cancel).

### Requirement: Meal-on reopens an order completed by meal-off

**Reason:** Subscriptions do not complete because of meal-off, so there is no completed-by-meal-off order to reopen.
**Migration:** Meal-on still reopens a customer-skipped slot to `scheduled` before the deadline; it MUST NOT create or reactivate a monthly `Order`.
