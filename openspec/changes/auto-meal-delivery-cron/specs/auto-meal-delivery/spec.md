## ADDED Requirements

### Requirement: Eligible slots are scheduled live meals for the period

The system SHALL select auto-delivery candidates as `OrderDelivery` rows where `service_date` equals the target business date, `meal_period` equals the job period (`lunch` or `dinner`), `status` is `scheduled`, and the parent order or subscription is live for that date (same live-parent rules used for kitchen/today-board eligibility). The system MUST NOT select slots that are already `delivered`, `skipped`, or `missed`.

#### Scenario: Customer meal-off excludes lunch

- **WHEN** a customer successfully meal-offs today's lunch slot before the meal-off deadline
- **AND** the lunch auto-delivery job runs for that service date
- **THEN** that slot MUST NOT be selected as a candidate

#### Scenario: Scheduled lunch on live subscription is selected

- **WHEN** an active subscription has a today's lunch slot still `scheduled`
- **AND** the lunch auto-delivery job runs for that service date
- **THEN** that slot MUST be included in the candidate set

#### Scenario: Cancelled subscription outside effective window is excluded

- **WHEN** a subscription is cancelled such that the slot's service date is not live under subscription parent rules
- **THEN** that slot MUST NOT be included in the candidate set

### Requirement: Auto-delivery reuses mark_delivery semantics

For each candidate, the system SHALL mark the slot delivered by invoking the same domain path as admin mark-delivered (`mark_delivery` with `to_status=delivered`), including wallet debit via published slot final price, Onahar best-effort credit, and order completion rules. The system MUST NOT implement a separate status-only update that skips wallet charging.

#### Scenario: Successful auto-delivery charges wallet

- **WHEN** an eligible scheduled slot is processed by auto-delivery and the customer wallet is active with sufficient balance and a published slot price exists
- **THEN** the slot status becomes `delivered`, the wallet is debited once for that delivery, and `payment_status` reflects a successful charge

#### Scenario: Idempotent re-run does not double charge

- **WHEN** auto-delivery runs again for a slot already `delivered` and charged
- **THEN** the system MUST NOT create a second wallet debit for that delivery

### Requirement: Per-slot failures do not abort the batch

The system SHALL process candidates independently. If marking one slot fails (including insufficient funds, frozen wallet, or missing slot price), the system MUST leave that slot unchanged (still `scheduled` when the atomic mark rolled back), record the failure with a stable error code, and continue processing remaining candidates.

#### Scenario: One insufficient wallet continues batch

- **WHEN** two eligible lunch slots exist and the first customer's wallet balance is insufficient
- **AND** the second customer's wallet can pay
- **THEN** the first slot remains `scheduled`, the second becomes `delivered` and charged, and the run result reports one failure and one success

### Requirement: Lunch and dinner schedules are distinct jobs

The system SHALL support running auto-delivery for `lunch` and for `dinner` as separate invocations with an explicit meal period. Production scheduling MUST target approximately 15:00 Asia/Dhaka for lunch and 23:00 Asia/Dhaka for dinner unless operators change the managed crontab.

#### Scenario: Lunch job does not deliver dinner slots

- **WHEN** the auto-delivery command runs with `meal_period=lunch` for a given service date
- **THEN** dinner slots for that date MUST NOT be marked delivered by that run

#### Scenario: Dinner job uses business-local service date

- **WHEN** the dinner auto-delivery job runs near 23:00 in Asia/Dhaka
- **THEN** it MUST use the Asia/Dhaka calendar date as `service_date`, not an accidental UTC date shift

### Requirement: Dry-run does not mutate deliveries

The system SHALL provide a dry-run mode that reports how many slots would be processed without changing delivery status or wallet balances.

#### Scenario: Dry-run lists candidates only

- **WHEN** an operator runs auto-delivery with dry-run enabled for lunch on a date with N scheduled live lunch slots
- **THEN** the system reports N candidates and leaves all slots `scheduled` with no new meal-payment debits
