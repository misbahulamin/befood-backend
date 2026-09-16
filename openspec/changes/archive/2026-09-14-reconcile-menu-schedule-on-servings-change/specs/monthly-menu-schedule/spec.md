## ADDED Requirements

### Requirement: Draft schedule auto-reconciles when plan servings decrease

When a linked cycle plan's lines are replaced via servings matrix save and a draft monthly menu schedule exists for that plan, the system SHALL automatically remove excess slot assignments so that per-ingredient usage in the schedule does not exceed each plan line's new `servings_count`. The schedule row and all unaffected assignments MUST be preserved.

#### Scenario: Decrease by one removes one assignment

- **WHEN** a draft schedule assigns ingredient "Egg Curry" on 5 slots and the admin saves a plan matrix reducing Egg Curry `servings_count` from 5 to 4
- **THEN** exactly one Egg Curry slot assignment is removed, four remain, and the schedule is not deleted

#### Scenario: Decrease to zero removes all assignments

- **WHEN** a draft schedule assigns ingredient "Regular Egg Fry" on 1 slot and the admin saves a plan matrix setting that ingredient's `servings_count` to 0 or removing the ingredient from the plan
- **THEN** all Regular Egg Fry slot assignments are removed and quota summary shows `used = 0` and `over_quota = false`

#### Scenario: Increase does not auto-add assignments

- **WHEN** a draft schedule uses Chicken on 10 slots and the admin increases Chicken `servings_count` from 10 to 12
- **THEN** the schedule still has 10 Chicken assignments and remaining quota is 2 for manual assignment

#### Scenario: Save assignments succeeds after reconciliation

- **WHEN** a draft schedule was over quota before plan line save and reconciliation runs as part of the same plan line update
- **THEN** a subsequent assignment save or publish attempt is not blocked solely by the prior over-quota state for trimmed ingredients

#### Scenario: Published schedule not reconciled via plan line edit

- **WHEN** a plan has a published monthly menu schedule
- **THEN** plan line replacement is not allowed while finalized and reconciliation does not mutate published schedules

#### Scenario: Deterministic trim order

- **WHEN** reconciliation must remove N assignments for an ingredient
- **THEN** the system removes assignments from the latest `service_date` first and prefers `dinner` before `lunch` on the same date
