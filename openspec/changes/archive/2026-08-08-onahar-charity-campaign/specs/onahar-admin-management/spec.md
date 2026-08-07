## ADDED Requirements

### Requirement: Admin manages contribution target

The system SHALL provide verified-admin web APIs to read and update the global Onahar contribution target and to list target-change history (previous value, new value, actor, timestamp). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST receive `403`.

#### Scenario: Verified admin reads settings

- **WHEN** a verified admin requests Onahar settings
- **THEN** the system responds `200` with the current contribution target and related configuration fields

#### Scenario: Verified admin changes target with history

- **WHEN** a verified admin updates the contribution target to a valid new integer
- **THEN** the system MUST persist the new target and MUST append a history record with previous value, new value, actor, and timestamp

#### Scenario: Non-admin denied

- **WHEN** an authenticated customer calls the admin Onahar settings endpoint
- **THEN** the system responds `403 Forbidden`

### Requirement: Admin manages distributions end-to-end

The system SHALL provide verified-admin web APIs to create, update drafts, upload media, list/detail, publish, and cancel Onahar distribution campaigns. Publish and cancel MUST enforce fund ledger rules defined by the fund-and-distribution capability.

#### Scenario: Admin publishes via web API

- **WHEN** a verified admin publishes a valid draft distribution whose meal count is within available fund
- **THEN** the system responds with success, status `published`, and fund available meals reduced accordingly

#### Scenario: Admin lists distributions including drafts

- **WHEN** a verified admin lists distributions
- **THEN** draft, published, and cancelled campaigns MUST be visible according to allowlisted filters (unlike the public list)

### Requirement: Admin fund and audit visibility

The system SHALL provide verified-admin read APIs for current fund totals (contributed, distributed, available) and for Onahar audit log entries covering at least: target changes, contributions generated, contribution adjustments, monthly expiries, distribution created/edited/cancelled, fund deducted/restored, and media uploads. Each audit entry MUST include action, actor (when applicable), timestamp, and previous/new values when relevant.

#### Scenario: Admin reads fund summary

- **WHEN** a verified admin requests the Onahar fund summary
- **THEN** the system responds `200` with contributed, distributed, and available meal totals consistent with the ledger

#### Scenario: Admin reads audit log after target change

- **WHEN** a verified admin changed the contribution target and then lists Onahar audit logs
- **THEN** an audit entry for the target change MUST appear with previous and new values
