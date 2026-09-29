## ADDED Requirements

### Requirement: Canonical cancel classifies each scheduled slot by meal-off cutoff

The system SHALL implement a single domain cancel operation for `CustomerSubscription` used by customer self-cancel and admin cancel. Within one database transaction, after locking the subscription row, the operation MUST set `status=cancelled`, set `cancelled_at` to the current UTC timestamp, and set `cancel_effective_on` to the current meal-off business date unless a documented equivalent rule is chosen. For every related `OrderDelivery` with `status=scheduled`, the operation MUST evaluate `is_past_meal_cutoff(service_date, meal_period)` using `MealOffSettings` timezone and lunch/dinner off times. If the cutoff has already passed (`business now` strictly after the deadline), the delivery MUST remain `scheduled` (finalized/preserved). If the cutoff has not passed (including exactly at the deadline), the delivery MUST be soft-cancelled as `status=skipped`, `skip_source=system`, with a stable cancel note, and MUST NOT be hard-deleted. Rows that are already `delivered`, `skipped`, or `missed` MUST NOT be altered. Lunch and dinner for the same `service_date` MUST be evaluated independently.

#### Scenario: Cancel before dinner cutoff skips dinner keeps lunch after lunch cutoff

- **WHEN** lunch cutoff has passed, dinner cutoff has not, and cancel runs for a subscription with both periods `scheduled` on the business date
- **THEN** lunch remains `scheduled`, dinner becomes `skipped` with system skip source, and the subscription is `cancelled`

#### Scenario: Cancel after both cutoffs preserves both same-day meals

- **WHEN** both lunch and dinner cutoffs have passed and cancel runs
- **THEN** both same-day `scheduled` deliveries remain `scheduled` and future-date `scheduled` deliveries become `skipped`

#### Scenario: Exact cutoff boundary still cancellable

- **WHEN** dinner off time is `16:00:00` and cancel runs at exactly that local deadline instant for a `scheduled` dinner
- **THEN** that dinner is soft-skipped (same comparison semantics as customer meal-off eligibility)

#### Scenario: Future dates are skipped

- **WHEN** cancel runs with `scheduled` deliveries on dates after the business today
- **THEN** those future deliveries become `skipped` with system skip source

#### Scenario: Delivered meals untouched

- **WHEN** a delivery is already `delivered` (charged or not) and cancel runs
- **THEN** that delivery’s status, payment fields, and wallet transaction link remain unchanged

### Requirement: Cancel is atomic and idempotent

The cancel operation MUST run inside an atomic transaction with a row lock on the subscription. If the subscription is already `cancelled`, the operation MUST return successfully without re-applying skip side effects that would duplicate financial or destructive outcomes (no double wallet adjustments; no changing already-finalized rows). Partial updates where the subscription is cancelled but cancellable future slots remain `scheduled`, or slots are skipped while the subscription stays `active`, MUST NOT occur.

#### Scenario: Repeat cancel is safe

- **WHEN** cancel is invoked twice for the same subscription
- **THEN** the second call succeeds without changing already-skipped or preserved rows into an inconsistent state and without creating duplicate wallet effects

#### Scenario: No active subscription for customer self-cancel

- **WHEN** a verified customer calls self-cancel with no active subscription
- **THEN** the API responds with not-found semantics consistent with the existing current-cancel endpoint
