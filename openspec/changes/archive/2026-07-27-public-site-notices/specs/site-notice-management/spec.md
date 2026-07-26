## ADDED Requirements

### Requirement: Admin can create and edit bilingual notices

The system SHALL allow Django Admin staff to create and update site notices. Each notice MUST have a unique `public_id`, bilingual title fields (`title_en`, `title_bn`), bilingual body fields (`body_en`, `body_bn`), a `severity` from the allowlisted set (`info`, `warning`, `critical`), an `is_published` flag, optional `publish_at` and `publish_until` timestamps (UTC), and a `sort_order` integer. At least one of `title_en` or `title_bn` MUST be non-empty.

#### Scenario: Create draft notice with both locales

- **WHEN** an admin creates a notice with English and Bangla titles/bodies and `is_published=false`
- **THEN** the system stores the notice as unpublished and it MUST NOT appear on the public active feed

#### Scenario: Create notice with only English title

- **WHEN** an admin creates a notice with a non-empty `title_en` and empty `title_bn`
- **THEN** the system accepts the notice

#### Scenario: Reject notice with empty titles in both locales

- **WHEN** an admin attempts to save a notice with both `title_en` and `title_bn` empty
- **THEN** the system rejects the save with a validation error

#### Scenario: Reject invalid severity

- **WHEN** an admin submits a severity outside `info`, `warning`, and `critical`
- **THEN** the system rejects the save with a validation error

### Requirement: Admin can publish and unpublish notices

The system SHALL allow admins to set `is_published` to true or false. Only notices that satisfy the active rule MAY appear on the public feed.

#### Scenario: Publish a draft

- **WHEN** an admin sets `is_published=true` on a draft notice whose schedule window includes now (or has no schedule bounds)
- **THEN** the notice becomes eligible for the public active feed

#### Scenario: Unpublish an active notice

- **WHEN** an admin sets `is_published=false` on a previously active notice
- **THEN** the notice MUST disappear from the public active feed immediately

### Requirement: Notice schedule window controls visibility

The system SHALL treat a published notice as active only when the current UTC time is within its schedule window: `publish_at` is null or `<= now`, and `publish_until` is null or `> now`. Expiry MUST NOT require a background job to flip `is_published`.

#### Scenario: Notice not yet started

- **WHEN** a published notice has `publish_at` in the future
- **THEN** the notice MUST NOT appear on the public active feed

#### Scenario: Notice expired by publish_until

- **WHEN** a published notice has `publish_until` in the past
- **THEN** the notice MUST NOT appear on the public active feed even if `is_published` remains true

#### Scenario: Open-ended published notice

- **WHEN** a published notice has null `publish_at` and null `publish_until`
- **THEN** the notice MUST appear on the public active feed

#### Scenario: Active within window

- **WHEN** a published notice has `publish_at <= now` and `publish_until > now`
- **THEN** the notice MUST appear on the public active feed

### Requirement: Admin list shows lifecycle status

The Django Admin notice list SHALL expose enough information for staff to distinguish draft, scheduled, active, and expired notices (via filters and/or a computed status display).

#### Scenario: Filter unpublished drafts

- **WHEN** an admin filters the notice list to unpublished notices
- **THEN** only notices with `is_published=false` are listed
