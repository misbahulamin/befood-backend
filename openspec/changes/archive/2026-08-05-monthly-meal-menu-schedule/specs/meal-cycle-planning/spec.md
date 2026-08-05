## ADDED Requirements

### Requirement: Finalized plan is prerequisite for monthly menu schedule

The system SHALL require a `MealCyclePlan` to be `finalized` before a monthly menu schedule may be created for that plan. Draft plans MUST NOT own a monthly menu schedule.

#### Scenario: Schedule create requires finalized plan

- **WHEN** a verified admin creates a monthly menu schedule for a finalized cycle plan
- **THEN** the system accepts the create

#### Scenario: Schedule create rejected for draft plan

- **WHEN** a verified admin creates a monthly menu schedule for a draft cycle plan
- **THEN** the system rejects the create with a validation error

## MODIFIED Requirements

### Requirement: Admin can reopen a finalized plan

The system SHALL allow a verified admin to reopen a finalized plan, returning it to `draft` so lines and margins can be edited again. If a monthly menu schedule exists for that plan, reopen MUST be rejected while the schedule is `published`; if the schedule is `draft`, reopen MUST either (a) reject until the schedule is deleted, or (b) delete/clear schedule assignments and then reopen — the chosen behavior MUST be consistent and documented, and MUST prevent quota-breaking orphan schedules.

#### Scenario: Reopen enables edits

- **WHEN** a verified admin reopens a finalized plan that has no monthly menu schedule
- **THEN** the plan status is `draft` and servings updates are accepted

#### Scenario: Reopen blocked while schedule published

- **WHEN** a verified admin attempts to reopen a finalized plan whose monthly menu schedule is `published`
- **THEN** the system rejects reopen with a conflict or validation error instructing to unpublish or remove the schedule first

#### Scenario: Reopen with draft schedule clears or blocks safely

- **WHEN** a verified admin reopens a finalized plan that has only a `draft` monthly menu schedule
- **THEN** the system either clears that schedule’s assignments (or deletes the schedule) as part of reopen, or rejects reopen until the draft schedule is removed — and MUST NOT leave a schedule that can exceed the reopened plan’s new quotas
