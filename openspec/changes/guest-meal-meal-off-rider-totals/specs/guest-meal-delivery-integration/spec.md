# Spec Delta

## Purpose

Defines how prepaid Guest Meals attach to subscription delivery stops, remain visible to kitchen and riders, and interact safely with Meal-OFF when cancel/refund is not yet available.

## ADDED Requirements

### Requirement: Guest Meal must link to a resolvable delivery stop

Successful Guest Meal create MUST attach the order to the customer’s subscription `OrderDelivery` for the same `service_date` and `meal_period`. The system MUST ensure or resolve that stop before debit persistence completes. If no valid stop can be resolved for the requested slot, create MUST fail without wallet debit and without persisting a Guest Meal.

#### Scenario: Create links to subscription stop

- **WHEN** an eligible Guest Meal create succeeds for `(D, lunch)`
- **THEN** the Guest Meal’s delivery reference points at the subscription lunch stop for `D`

#### Scenario: Unresolvable stop rejects create

- **WHEN** create cannot resolve a subscription delivery stop for the requested date and period
- **THEN** the system rejects the request, creates no Guest Meal, and does not debit the wallet

### Requirement: Parent deliver syncs Guest Meal status without re-charging guests

When the linked parent delivery becomes delivered, linked scheduled Guest Meals MUST transition to delivered. The regular charge-on-delivery path MUST NOT debit Guest Meal totals again.

#### Scenario: Parent delivered flips guest status

- **WHEN** the linked `OrderDelivery` is marked delivered and linked Guest Meals are scheduled
- **THEN** those Guest Meals become delivered

#### Scenario: Deliver does not re-charge guest totals

- **WHEN** a parent stop with prepaid Guest Meals is charged on deliver
- **THEN** the wallet debit for that delivery covers only the regular meal charge rules and does not include guest prepaid totals

### Requirement: Cancelled Guest Meals are excluded from operational counts

Kitchen demand and rider guest quantity aggregations MUST exclude cancelled Guest Meals and MUST sum quantity across multiple non-cancelled Guest Meals linked to the same delivery stop.

#### Scenario: Multiple guest orders aggregate

- **WHEN** two scheduled Guest Meals with quantities 2 and 3 are linked to the same delivery
- **THEN** guest quantity for that stop is `5`

#### Scenario: Cancelled guest quantity excluded

- **WHEN** a cancelled Guest Meal and a scheduled Guest Meal share a delivery
- **THEN** only the scheduled quantity contributes to guest operational counts

### Requirement: Existing Guest Meals are not silently discarded on Meal-OFF

Because Guest Meal cancel/refund is out of scope for this change, the system MUST NOT silently cancel, refund, or drop paid Guest Meals when a customer attempts Meal-OFF. Operational visibility of unpaid-regular / paid-guest combinations MUST be prevented by the Meal-OFF blocking rule defined under customer-meal-off rather than by orphaning guest rows.

#### Scenario: No silent guest cancel on meal-off attempt

- **WHEN** a customer with a scheduled Guest Meal for `(D, lunch)` attempts lunch Meal-OFF
- **THEN** the system does not cancel or refund that Guest Meal as a side effect of the attempt
