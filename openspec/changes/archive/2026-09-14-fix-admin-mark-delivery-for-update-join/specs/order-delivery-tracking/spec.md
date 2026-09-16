## ADDED Requirements

### Requirement: Admin mark works for subscription-owned deliveries

The system SHALL allow an authorized admin (or kitchen operator with permission) to mark a `scheduled` delivery as `delivered` or `skipped` when the delivery is owned by a **subscription** (`subscription` set, `order` may be null), using the same status, audit, and progress rules as order-owned deliveries. Success MUST persist delivery state changes and MUST NOT return a server error caused by database row-locking combined with nullable parent joins.

#### Scenario: Admin marks subscription lunch delivered

- **WHEN** an authorized admin posts mark with status `delivered` for a scheduled lunch delivery on an active subscription under PostgreSQL
- **THEN** the system responds successfully (not `500`), the delivery status is `delivered`, and who marked it is recorded

#### Scenario: Admin marks subscription dinner skipped

- **WHEN** an authorized admin posts mark with status `skipped` for a scheduled dinner delivery on a subscription under PostgreSQL
- **THEN** the system responds successfully (not `500`), the delivery status is `skipped`, and `skip_source` is `admin`

#### Scenario: Order-owned admin mark still succeeds

- **WHEN** an authorized admin marks a scheduled delivery on a legacy monthly/daily **order** parent as `delivered` or `skipped`
- **THEN** the mark succeeds with the same status and audit behaviour as today

### Requirement: Admin mark row lock must be Postgres-safe with nullable parents

When locking an `OrderDelivery` for admin mark delivered or skipped, the system MUST acquire a row lock on the delivery in a way that PostgreSQL accepts when `order` and/or `subscription` foreign keys are nullable (no `FOR UPDATE` on the nullable side of an outer join). Concurrent mark attempts on the same delivery MUST still be serialized by locking that delivery row.

#### Scenario: Locking a subscription-owned delivery for mark does not raise FOR UPDATE outer-join error

- **WHEN** `mark_delivery` runs for a delivery with `subscription` set and `order` null (or the reverse) under PostgreSQL
- **THEN** the operation completes without `NotSupportedError` / `FOR UPDATE cannot be applied to the nullable side of an outer join`
