## Purpose

Onahar contribution engine: credit points from delivered meals, monthly cycles with target snapshots, multi-contribution math, refunds/reversals, and idempotent month close.

## Requirements

### Requirement: Eligible delivered meals credit Onahar points

The system SHALL credit exactly one Onahar Point to a registered customer when an `OrderDelivery` belonging to that customer first becomes `delivered`. The system MUST NOT credit points for `skipped`, `missed`, `scheduled`, cancelled orders, or non-delivered states. The system MUST associate each credit with the source `OrderDelivery` and MUST prevent duplicate credits for the same delivery.

#### Scenario: First delivery marks one point

- **WHEN** an authorized operator successfully marks a customer's scheduled delivery as `delivered`
- **THEN** the system MUST create exactly one credit Onahar point event for that delivery and increase that customer's current calendar-month net points by 1

#### Scenario: Duplicate mark does not double credit

- **WHEN** the same delivery is marked `delivered` again or the credit processor runs twice for that delivery
- **THEN** the system MUST NOT create a second credit point event and MUST leave monthly net points unchanged from the first credit

#### Scenario: Skipped meal does not credit

- **WHEN** a delivery is marked `skipped`
- **THEN** the system MUST NOT create an Onahar point credit for that delivery

### Requirement: Monthly cycle independence and target snapshot

The system SHALL calculate Onahar progress per customer per calendar month (`YYYY-MM` in the project timezone). Incomplete points from a closed month MUST NOT carry forward into a later month. Each monthly progress cycle MUST store a `target_snapshot` equal to the configured contribution target applicable when the cycle is first opened, and subsequent contribution math for that cycle MUST use that snapshot even if the global target later changes.

#### Scenario: Incomplete points do not carry forward

- **WHEN** a customer has 40 net points in a month whose target snapshot is 45 and that month is closed
- **THEN** the system MUST record 0 contributions for that month, MUST expire the remaining 40 points in history, and MUST start the next month at 0 points

#### Scenario: Historical month keeps old target

- **WHEN** an admin changes the global contribution target from 50 to 40 after a prior month cycle already stored target snapshot 50
- **THEN** recalculation or display of that prior month MUST continue to use target 50

### Requirement: Multiple contributions within one month

The system SHALL allow multiple Onahar Meal contributions in the same month when net eligible points reach whole multiples of the cycle `target_snapshot`. The system MUST set earned contributions to `floor(net_points / target_snapshot)` and remaining points to `net_points % target_snapshot`. When net points cross a new multiple during an open month, the system MUST create contribution records and fund credits for the newly earned meals without waiting for month end.

#### Scenario: 120 points with target 50 yields two contributions

- **WHEN** a customer's open monthly cycle has target snapshot 50 and net eligible points become 120
- **THEN** the system MUST record 2 Onahar Meal contributions for that customer-month and MUST leave 20 remaining points

#### Scenario: Crossing threshold mid-month credits fund immediately

- **WHEN** a customer's net points move from 49 to 50 against target snapshot 50
- **THEN** the system MUST create 1 contribution record and MUST credit the Onahar Fund ledger by 1 meal in the same processing transaction

### Requirement: Configurable contribution target with change history

The system SHALL maintain a global Onahar contribution target (default 50, integer ≥ 1) editable by verified admins. Each target change MUST record previous value, new value, actor, and timestamp. Changing the target MUST NOT rewrite closed monthly cycles' snapshots.

#### Scenario: Admin updates target

- **WHEN** a verified admin sets the contribution target from 50 to 45
- **THEN** the system MUST persist current target 45 and MUST append a target-change history row with previous 50, new 45, actor, and timestamp

#### Scenario: Invalid target rejected

- **WHEN** a verified admin attempts to set the contribution target to 0 or a non-integer value
- **THEN** the system MUST reject the change with a validation error and MUST leave the previous target unchanged

### Requirement: Refund and reversal adjustments

The system SHALL reverse an Onahar point credit when a previously credited delivery is refunded or otherwise undone after credit. The system MUST write an auditable reverse point event tied to that delivery at most once. If contributions already issued for the month exceed `floor(new_net_points / target_snapshot)`, the system MUST create compensating contribution/fund adjustment records so public totals remain consistent, and MUST NOT silently delete historical contribution rows.

#### Scenario: Refund reverses a point

- **WHEN** a delivery that previously credited +1 point is refunded
- **THEN** the system MUST record a −1 reverse point event for that delivery and MUST decrease the month's net points by 1

#### Scenario: Refund after contribution creates adjustment

- **WHEN** a refund reduces net points such that previously issued contributions exceed the new floor division result
- **THEN** the system MUST create compensating adjustment records against contributions and/or the fund ledger and MUST retain the original contribution rows for audit

### Requirement: Idempotent monthly close job

The system SHALL provide an idempotent month-close process that finalizes a calendar month: confirms contributions already earned, expires remaining incomplete points into history, marks the cycle closed, and writes an audit entry. Re-running the job for an already closed month MUST NOT create duplicate contributions, duplicate expiries, or duplicate fund credits.

#### Scenario: Close month expires remainder

- **WHEN** the month-close job runs for a month where a customer has 20 remaining points after contributions
- **THEN** those 20 points MUST be marked expired in history and MUST NOT convert into a contribution

#### Scenario: Re-run is safe

- **WHEN** the month-close job runs again for the same already-closed month
- **THEN** the system MUST NOT create additional contributions, expiries, or fund ledger credits for that month
