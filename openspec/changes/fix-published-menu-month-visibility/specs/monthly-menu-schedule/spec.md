## MODIFIED Requirements

### Requirement: Schedule draft and publish lifecycle for kitchen use

The system SHALL support schedule statuses `draft` and `published`. Only verified admins MAY create, edit, publish, or unpublish schedules. Full-month schedule detail MUST NOT be exposed on public unauthenticated meal APIs except through the dedicated public package menu endpoint, which returns published slot contents only for the requested calendar month matching the linked cycle's `(year, month)`. Publishing a schedule for cycle month M makes that package's menu visible to customers and marketing pages only when clients query year/month M (or when discovery metadata directs them to M). Published schedules are the source of truth for customer today's-menu data for that package and month.

#### Scenario: Draft edits allowed

- **WHEN** a schedule is `draft` and a verified admin updates slot assignments within quotas
- **THEN** the system accepts the update

#### Scenario: Published schedule still admin-readable for kitchen prep

- **WHEN** a verified admin requests the full monthly schedule for a published schedule
- **THEN** the system returns all dates and meal periods with assigned ingredients for kitchen preparation

#### Scenario: Unauthenticated full-month access denied

- **WHEN** an unauthenticated client requests a full monthly menu schedule
- **THEN** the system returns `401` or otherwise denies access

#### Scenario: Customer visibility scoped to published cycle month

- **WHEN** an admin publishes the September 2026 schedule for Student Package
- **THEN** public and customer menu APIs return published slot contents for `year=2026&month=9` and return `schedule_published` false with empty days for `year=2026&month=8` until August is separately published
