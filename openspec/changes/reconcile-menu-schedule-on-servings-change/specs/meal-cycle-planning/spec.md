## ADDED Requirements

### Requirement: Servings matrix save reconciles linked draft menu schedule

When a verified admin replaces plan lines on a draft cycle plan via `PUT /meals/cycle-plans/{public_id}/lines/`, the system MUST reconcile any linked draft monthly menu schedule in the same transaction so schedule usage matches the new plan-line quotas. The operation MUST NOT delete the schedule.

#### Scenario: Matrix save triggers reconciliation

- **WHEN** a verified admin saves the servings matrix on a draft plan that has a draft monthly menu schedule with assignments
- **THEN** plan lines update and the linked schedule assignments are trimmed as needed without deleting the schedule

#### Scenario: Matrix save with no schedule is unchanged

- **WHEN** a verified admin saves the servings matrix on a draft plan with no monthly menu schedule
- **THEN** only plan lines are updated and no schedule rows are created
