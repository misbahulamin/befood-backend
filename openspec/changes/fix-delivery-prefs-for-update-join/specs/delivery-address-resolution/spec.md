## ADDED Requirements

### Requirement: Future scheduled snapshot resync is Postgres-safe with nullable parents

When the system re-resolves and updates address snapshots for future `scheduled` `OrderDelivery` rows (for example after a customer changes meal delivery preferences or places), it MUST acquire any row lock in a way that PostgreSQL accepts when `order` and/or `subscription` foreign keys are nullable (no `FOR UPDATE` on the nullable side of an outer join). Concurrent resyncs that update the same delivery MUST still be serialized by locking that delivery row. Deliveries that are not future `scheduled` MUST NOT have their address snapshots rewritten.

#### Scenario: Resync with subscription-owned future deliveries does not raise FOR UPDATE outer-join error

- **WHEN** a customer with at least one future `scheduled` delivery that has `subscription` set and `order` null changes delivery preferences (or the system otherwise runs future scheduled snapshot resync for that customer) under PostgreSQL
- **THEN** the operation completes without `NotSupportedError` / `FOR UPDATE cannot be applied to the nullable side of an outer join`, and those future scheduled rows receive the newly resolved snapshot

#### Scenario: Resync with order-owned future deliveries still succeeds

- **WHEN** a customer with future `scheduled` order-owned deliveries (subscription null) changes delivery preferences under PostgreSQL
- **THEN** the resync completes successfully and those future scheduled snapshots update as before

#### Scenario: Non-scheduled historical snapshots remain unchanged

- **WHEN** a customer changes preferences and has a past or non-`scheduled` delivery (for example `delivered`)
- **THEN** that delivery’s address snapshot remains unchanged
