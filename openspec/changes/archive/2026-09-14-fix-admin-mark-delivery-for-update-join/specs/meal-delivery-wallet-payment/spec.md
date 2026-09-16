## ADDED Requirements

### Requirement: Delivered charge lock is Postgres-safe for subscription-owned slots

When locking an `OrderDelivery` to debit the customer wallet after a transition to `delivered`, the system MUST acquire a row lock on the delivery in a way that PostgreSQL accepts when `order` and/or `subscription` foreign keys are nullable (no `FOR UPDATE` on the nullable side of an outer join). Charge amount, idempotency, and debit-only-on-delivered rules from this capability remain unchanged.

#### Scenario: Charge after admin mark delivered on subscription does not raise FOR UPDATE outer-join error

- **WHEN** an authorized admin marks a subscription-owned `scheduled` delivery as `delivered` with sufficient wallet balance under PostgreSQL
- **THEN** the mark and wallet charge complete without `NotSupportedError` / `FOR UPDATE cannot be applied to the nullable side of an outer join`
- **AND** exactly one completed payment debit exists for that delivery when charging is enabled

#### Scenario: Admin skip still does not charge

- **WHEN** an authorized admin marks a subscription-owned delivery as `skipped`
- **THEN** the system does not debit the wallet for that slot
