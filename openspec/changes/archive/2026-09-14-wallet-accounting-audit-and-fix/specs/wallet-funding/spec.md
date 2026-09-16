## ADDED Requirements

### Requirement: Provider recharge duplicate checks ignore failed refs
When creating a customer provider recharge request (`bkash`/`nagad`/`bank` with non-empty `transaction_id`), the funding service MUST reject the request as a duplicate only if a matching recharge `external_ref` already exists in `pending` or `completed` status. Failed or cancelled prior requests with the same provider ref MUST be ignored for duplicate detection. Manual recharge flows without provider refs remain unchanged. Admin approve/reject endpoints, notification scheduling, and Admin Wallet custody sync on approve MUST remain behaviorally unchanged except for this uniqueness rule.

#### Scenario: Reuse after reject succeeds
- **WHEN** the only prior row for method `bkash` and `external_ref=TX12345` is `status=failed`
- **THEN** `request_recharge` creates a new pending recharge for that ref

#### Scenario: Duplicate of approved recharge still fails
- **WHEN** a completed `bkash` recharge already exists with `external_ref=TX12345`
- **THEN** `request_recharge` with the same method and transaction id raises the existing duplicate-provider-ref error without creating a new row
