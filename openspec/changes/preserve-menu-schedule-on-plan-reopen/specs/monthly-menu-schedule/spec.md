## ADDED Requirements

### Requirement: Draft schedule survives plan reopen and line edits

The system SHALL keep an existing `draft` monthly menu schedule and its slot assignments when the linked cycle plan is reopened or when plan lines are replaced via servings matrix save. Schedule creation for a plan without a schedule MUST still require the plan to be `finalized`. Assignment save and publish MUST continue to enforce per-ingredient quota against the current plan lines.

#### Scenario: Draft schedule readable while plan is draft after reopen

- **WHEN** a verified admin reopens a finalized plan that has a draft schedule with assignments
- **THEN** the admin can retrieve the schedule detail and assignments without recreating the schedule

#### Scenario: Over-quota assignments blocked on save after servings shrink

- **WHEN** a plan line’s `servings_count` is reduced below the number of slot assignments for that ingredient and the admin attempts to save or publish the schedule
- **THEN** the system rejects the operation with a quota validation error and does not silently delete assignments

#### Scenario: Schedule create still requires finalized plan

- **WHEN** a verified admin attempts to create a new monthly menu schedule for a draft cycle plan that has no existing schedule
- **THEN** the system rejects the request with a validation error
