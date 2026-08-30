## ADDED Requirements

### Requirement: Meal-off and meal-on work for subscription-owned deliveries

The system SHALL allow a verified customer who owns a **subscription** to meal-off a `scheduled` delivery slot belonging to that subscription, and to meal-on a customer-skipped slot on that subscription, using the same deadline, ownership, and status rules as order-owned deliveries. Success MUST persist delivery state changes and MUST NOT return a server error caused by database row-locking combined with nullable parent joins. Parent may have `order` null and `subscription` set.

#### Scenario: Subscription lunch meal-off before deadline

- **WHEN** a verified customer posts meal-off for a scheduled lunch delivery on their active subscription while before the lunch deadline
- **THEN** the system responds successfully (not `500`), the delivery status is `skipped`, and `skip_source` is `customer`

#### Scenario: Subscription dinner meal-on before deadline

- **WHEN** a verified customer has meal-offed a dinner slot on their subscription and posts meal-on while before the dinner deadline
- **THEN** the system responds successfully, the delivery status is `scheduled`, and no wallet debit is created for that action

### Requirement: Meal toggle row lock must be Postgres-safe with nullable parents

When locking an `OrderDelivery` for customer meal-off or meal-on, the system MUST acquire a row lock on the delivery in a way that PostgreSQL accepts when `order` and/or `subscription` foreign keys are nullable (no `FOR UPDATE` on the nullable side of an outer join). Concurrent meal-off/on attempts on the same delivery MUST still be serialized by locking that delivery row.

#### Scenario: Locking a subscription-owned delivery does not raise FOR UPDATE outer-join error

- **WHEN** `customer_meal_off` or `customer_meal_on` runs for a delivery with `subscription` set and `order` null (or the reverse) under PostgreSQL
- **THEN** the operation completes without `NotSupportedError` / `FOR UPDATE cannot be applied to the nullable side of an outer join`

#### Scenario: Order-owned meal-off still succeeds

- **WHEN** a verified customer meal-offs a scheduled delivery on a legacy monthly/daily **order** parent while before the deadline
- **THEN** the meal-off succeeds with `skipped` / `skip_source=customer` as today
