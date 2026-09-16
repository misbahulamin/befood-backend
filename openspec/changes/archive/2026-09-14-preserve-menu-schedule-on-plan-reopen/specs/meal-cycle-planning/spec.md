## MODIFIED Requirements

### Requirement: Admin can reopen a finalized plan

The system SHALL allow a verified admin to reopen a finalized plan, returning it to `draft` so lines and margins can be edited again. If a monthly menu schedule exists for that plan, reopen MUST be rejected while the schedule is `published`. If the schedule is `draft`, reopen MUST preserve the schedule row and all existing slot assignments unchanged. Reopen MUST NOT delete, clear, or recreate the monthly menu schedule. Quota consistency after plan-line edits MUST be enforced by existing assignment save and publish validation, not by destructive schedule removal on reopen.

#### Scenario: Reopen enables edits

- **WHEN** a verified admin reopens a finalized plan that has no monthly menu schedule
- **THEN** the plan status is `draft` and servings updates are accepted

#### Scenario: Reopen blocked while schedule published

- **WHEN** a verified admin attempts to reopen a finalized plan whose monthly menu schedule is `published`
- **THEN** the system rejects reopen with a conflict or validation error instructing to unpublish or remove the schedule first

#### Scenario: Reopen with draft schedule preserves assignments

- **WHEN** a verified admin reopens a finalized plan that has a `draft` monthly menu schedule with day-wise slot assignments
- **THEN** the plan status becomes `draft`, the schedule row remains linked to the plan, and all prior slot assignments are unchanged

#### Scenario: Servings edit after reopen preserves schedule

- **WHEN** a verified admin reopens a finalized plan with a draft schedule, then updates plan lines via servings matrix save without deleting ingredients from the schedule
- **THEN** the monthly menu schedule and its slot assignments remain unchanged and quota summary reflects updated plan line servings

#### Scenario: Re-finalize after reopen keeps single schedule

- **WHEN** a verified admin reopens a plan with an existing draft schedule, edits plan lines, and finalizes again
- **THEN** exactly one monthly menu schedule remains for that plan with the same assignments as before finalize
