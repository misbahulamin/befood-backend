## ADDED Requirements

### Requirement: Historical charged deliveries can be backfilled into the profit ledger
The system SHALL provide a management command that creates missing profit ledger records for existing `OrderDelivery` rows that are already charged but lack a profit row. The command MUST reuse the same recognition helper and snapshot rules as live delivery recognition. The command MUST be safe to re-run (idempotent): deliveries that already have a profit row MUST be skipped without creating duplicates.

#### Scenario: Backfill creates rows for historical charged deliveries
- **WHEN** an operator runs the backfill command against a database containing charged deliveries without profit rows
- **THEN** profit ledger records are created for those deliveries using published slot snapshots available for each delivery’s package, service date, and meal period

#### Scenario: Re-running backfill does not duplicate
- **WHEN** the backfill command is run a second time on the same data
- **THEN** no additional profit rows are created for deliveries that already have ledger records

### Requirement: Backfill supports dry-run and validation against prior live aggregation
The system MUST support a dry-run mode that reports how many rows would be created without writing. The system MUST provide a validation path that compares ledger profit totals to the previous live calculator (`meal_profit_recognized` / package breakdown) for a documented window and reports mismatches for operator review before trusting the new dashboard.

#### Scenario: Dry-run reports without writing
- **WHEN** an operator runs backfill in dry-run mode
- **THEN** the command reports candidate counts and does not insert profit ledger rows

#### Scenario: Validation compares ledger to live calculator
- **WHEN** an operator runs validation after backfill for the overlapping historical window
- **THEN** the command reports ledger totals versus live aggregation totals so operators can confirm migration correctness (documenting any intentional axis differences such as `service_date` vs `updated_at`)
