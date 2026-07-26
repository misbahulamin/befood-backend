## Purpose

Persistent announcement/promotion records with typed categories, severity, optional banner image and CTA, publish schedule, and priority ordering.

## Requirements

### Requirement: Announcement record fields
The system SHALL persist announcement/promotion records with a stable `public_id`, required non-blank `title`, optional `description`, `type`, `severity`, optional banner `image`, optional `button_text` and `button_url`, `is_published`, optional `publish_at` and `publish_until`, integer `priority` (default 0), and `created_at` / `updated_at` timestamps.

#### Scenario: Supported type values
- **WHEN** an announcement is saved with a type value
- **THEN** the type MUST be one of `notice`, `offer`, `new_package`, `maintenance`, or `announcement`

#### Scenario: Supported severity values
- **WHEN** an announcement is saved with a severity value
- **THEN** the severity MUST be one of `info`, `warning`, `success`, or `error`

#### Scenario: Schedule window validation
- **WHEN** both `publish_at` and `publish_until` are provided
- **THEN** the system MUST reject the save if `publish_until` is not after `publish_at`

#### Scenario: CTA pairing validation
- **WHEN** `button_text` is non-empty and `button_url` is empty or invalid
- **THEN** the system MUST reject the save with a field validation error

#### Scenario: Optional promotional image
- **WHEN** an announcement is created without an image
- **THEN** the record MUST save successfully with a null/empty image

### Requirement: Priority ordering semantics
The system SHALL treat higher `priority` values as higher display precedence for active announcement feeds.

#### Scenario: Higher priority wins
- **WHEN** two active announcements differ only by priority
- **THEN** the higher priority announcement MUST appear first in the active feed ordering
