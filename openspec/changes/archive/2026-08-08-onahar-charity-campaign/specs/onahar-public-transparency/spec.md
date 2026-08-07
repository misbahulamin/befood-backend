## ADDED Requirements

### Requirement: Public overall statistics

The system SHALL expose an unauthenticated endpoint that returns Onahar overall statistics derived from live data, including at least: total meals contributed, total meals distributed, currently available meals, total contributors, total distribution campaigns, current month contributions, and current contribution target. Values MUST NOT be hard-coded marketing constants.

#### Scenario: Anonymous visitor reads stats

- **WHEN** an unauthenticated client requests public Onahar stats
- **THEN** the system responds `200` with the statistics fields above computed from Onahar records and ledgers

#### Scenario: Stats reflect new contribution

- **WHEN** a new contribution credits the fund by 1 meal
- **THEN** a subsequent public stats response MUST increase total meals contributed (and available meals, absent new distributions) accordingly

### Requirement: Public contributor leaderboard

The system SHALL expose an unauthenticated paginated leaderboard of contributors ranked by total Onahar meals contributed (descending, with deterministic tie-break). Each row MUST include a privacy-safe display name and contribution total. The system MUST NEVER include email, phone, address, or internal numeric user IDs in leaderboard payloads.

#### Scenario: Leaderboard orders by contribution total

- **WHEN** contributors have totals 24, 19, and 17 meals
- **THEN** the public leaderboard MUST list them in that descending order with privacy-safe display names

#### Scenario: Anonymous privacy mode

- **WHEN** a high-contributing customer has privacy preference `anonymous`
- **THEN** their leaderboard display name MUST be an anonymous label and MUST NOT reveal their real name

#### Scenario: Partial privacy mode

- **WHEN** a customer named appropriately for masking has privacy preference `partial`
- **THEN** the leaderboard MUST show a partially masked name (for example initials with obscured characters) rather than the full name

### Requirement: Public transparency ledger

The system SHALL expose an unauthenticated paginated transparency ledger showing contribution-side entries (date, privacy-safe display name, meals contributed) and distribution-side entries (date, location, meals used, campaign reference). Sensitive customer fields MUST NOT appear.

#### Scenario: Visitor reads mixed ledger

- **WHEN** an unauthenticated client requests the public Onahar ledger
- **THEN** the system responds `200` with paginated entries that include contribution and/or distribution sides without private customer identifiers

### Requirement: Public distribution history and detail

The system SHALL expose unauthenticated list and detail endpoints for published distribution campaigns, including campaign photo(s), location, date, meals distributed, and short description on list cards, and fuller detail (address, description, media gallery) on detail. Draft distributions MUST NOT appear on public endpoints. Cancelled campaigns MUST be omitted from the default public list or clearly marked per documented behavior (default: omit from default list).

#### Scenario: Public list shows published campaigns

- **WHEN** an unauthenticated client lists public distributions
- **THEN** only published campaigns MUST appear with location, date, meals distributed, and media preview when available

#### Scenario: Draft hidden from public

- **WHEN** a distribution exists in `draft` status
- **THEN** public list and detail MUST NOT expose that draft campaign

#### Scenario: Public detail by public id

- **WHEN** an unauthenticated client requests a published distribution by `public_id`
- **THEN** the system responds `200` with detail fields and media proofs
