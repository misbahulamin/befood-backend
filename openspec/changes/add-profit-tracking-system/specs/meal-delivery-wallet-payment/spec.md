## ADDED Requirements

### Requirement: Successful meal charge recognizes profit ledger entry
When a meal-delivery wallet charge succeeds for a `delivered` `OrderDelivery` (including idempotent re-attach of an existing completed meal-payment debit), the system MUST ensure a corresponding immutable profit ledger record exists for that delivery, using published slot snapshot recognition rules. The profit write MUST participate in the same database transaction boundary as the successful delivery/charge path so that a rolled-back charge does not leave a profit row, and a committed charge does not silently omit profit recognition (gaps MAY only be repaired by the documented backfill command).

#### Scenario: Auto or manual delivered charge creates profit
- **WHEN** auto-delivery cron or an admin marks a delivery `delivered` and the wallet charge succeeds
- **THEN** a profit ledger record exists for that delivery after the operation commits

#### Scenario: Charge failure creates neither debit nor profit
- **WHEN** mark-delivered fails because the wallet cannot be charged
- **THEN** no completed meal-payment debit and no profit ledger record exist for that attempt

#### Scenario: Idempotent already-charged path still ensures profit row
- **WHEN** a delivery is already `delivered` and charged, and mark-delivered/charge runs again
- **THEN** the wallet is not debited again and exactly one profit ledger record exists for that delivery
