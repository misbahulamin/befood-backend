## Purpose

Onahar fund ledger in meal units and distribution campaign lifecycle (draft, publish, cancel, media proofs).

## Requirements

### Requirement: Meal-unit fund ledger

The system SHALL maintain the Onahar Fund in meal units using an append-only ledger. Every fund change MUST create a ledger entry with direction (`credit` or `debit`), positive meal count, entry type, timestamp, and linkage to the source contribution or distribution when applicable. Available meals MUST equal total credited meals minus total debited meals and MUST be derived from ledger data (optionally with a denormalized cache updated in the same transaction).

#### Scenario: Contribution credits fund

- **WHEN** a customer earns one Onahar Meal contribution
- **THEN** the system MUST append a fund ledger credit of 1 meal linked to that contribution

#### Scenario: Available meals computed from ledger

- **WHEN** total contribution credits equal 1500 meals and total distribution debits equal 900 meals
- **THEN** available Onahar Fund meals MUST equal 600

### Requirement: Create distribution campaigns

The system SHALL allow verified admins to create distribution campaign records containing at least: title, location, full address, distribution date, meals to distribute, description, optional beneficiary notes, creator, and timestamps. Draft distributions MUST NOT debit the fund until published.

#### Scenario: Admin creates draft distribution

- **WHEN** a verified admin creates a distribution with title, location, date, and meal count
- **THEN** the system MUST store the campaign as `draft` and MUST NOT change available fund meals

#### Scenario: Non-admin cannot create distribution

- **WHEN** an authenticated customer attempts to create a distribution
- **THEN** the system MUST respond `403 Forbidden`

### Requirement: Publish distribution debits fund

The system SHALL debit the Onahar Fund when a verified admin publishes a draft distribution. Publish MUST run in a transaction that validates `meals_distributed <= available_meals`, appends a fund ledger debit linked to the distribution, and sets status to `published` with publisher and published timestamp. After publish, the distributed meal count MUST be immutable.

#### Scenario: Successful publish reduces available fund

- **WHEN** available fund is 1000 meals and a verified admin publishes a distribution of 250 meals
- **THEN** the system MUST append a 250-meal debit and available fund MUST become 750

#### Scenario: Over-fund distribution rejected

- **WHEN** available fund is 100 meals and a verified admin attempts to publish a distribution of 250 meals
- **THEN** the system MUST reject the publish with a conflict or validation error and MUST leave fund balance and distribution status unchanged

### Requirement: Cancel published distribution restores fund

The system SHALL allow verified admins to cancel a published distribution. Cancellation MUST append a compensating fund ledger credit restoring the previously debited meals, MUST set status to `cancelled`, and MUST retain media and audit history.

#### Scenario: Cancel restores meals

- **WHEN** a published 250-meal distribution is cancelled by a verified admin
- **THEN** the system MUST credit 250 meals back to the fund via ledger and MUST mark the distribution cancelled

### Requirement: Distribution media proofs

The system SHALL allow verified admins to attach one or more images (and optional future media URL fields) to a distribution campaign as proof. Public consumers MUST be able to read media URLs for published (non-cancelled or as documented) distributions without authentication. Uploads MUST validate allowed content types and size limits.

#### Scenario: Admin uploads proof image

- **WHEN** a verified admin uploads a valid image to a distribution
- **THEN** the system MUST store the media record linked to that distribution and expose a retrievable media URL

#### Scenario: Invalid media rejected

- **WHEN** a verified admin uploads an unsupported file type or oversized file
- **THEN** the system MUST reject the upload with a validation error and MUST NOT store the file as distribution media
