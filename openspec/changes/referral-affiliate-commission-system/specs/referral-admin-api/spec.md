## ADDED Requirements

### Requirement: Admin can view referral analytics summary including conversion metrics
The system SHALL provide a verified-admin analytics endpoint returning overall referral metrics for a date range, including: total referral relationships, total distinct active referrers, total commission paid (`success` amounts), total Admin Wallet commission deductions, total referral validations, total successful referral registrations, total paid subscribers originating from referral, and conversion rate derived from validations and successful registrations (zero-safe). Metrics MUST be derived from referral relationships, commission ledger, and validation events (or equivalent recorded validate outcomes). Documentation MUST state that “clicks” in v1 are represented by validation attempts unless a dedicated click tracker is added later.

#### Scenario: Admin loads analytics with conversion fields
- **WHEN** a verified admin requests referral analytics for a date range
- **THEN** the system responds `200` with financial totals and conversion metrics including validations, registrations, paid-from-referral count, and conversion rate

#### Scenario: Non-admin cannot access analytics
- **WHEN** a customer requests the admin referral analytics endpoint
- **THEN** the system responds `401` or `403`

### Requirement: Admin can list relationships and commissions with filters
The system SHALL provide paginated verified-admin list endpoints for referral relationships and commission records. Supported filters MUST include date range, user (referrer and/or referred public id), referral code, and commission status. Each commission row MUST expose audit fields needed for finance review (parties, meal, amounts, status, wallet references, timestamps).

#### Scenario: Filter commissions by referral code
- **WHEN** an admin lists commissions filtered by a referral code
- **THEN** only commissions originating from that referrer’s code relationships are returned

#### Scenario: Filter relationships by date range
- **WHEN** an admin lists relationships with `created_from` and `created_to`
- **THEN** only relationships attributed in that inclusive range are returned

### Requirement: Admin can retrieve per-customer referral detail
The system SHALL provide a verified-admin detail endpoint for a customer public id showing whether the customer is a referrer and/or referred, their referral code, referred-user list summary, lifetime and period earnings as referrer, and commission history generated as referrer and/or caused as referred.

#### Scenario: Admin opens customer referral detail
- **WHEN** a verified admin requests referral detail for a customer public id
- **THEN** the system responds `200` with that customer’s referral code, relationships, and earning summaries

### Requirement: Admin can export referral commission reports as CSV
The system SHALL provide a verified-admin CSV export for referral commission reports using the same filter set as the commission list (date range, user, referral code, status). The export MUST include finance-relevant columns: commission public id, status, referrer, referred, meal/delivery identifiers, meal date, meal price, percentage, commission amount, admin debit reference, user credit reference, and created timestamp.

#### Scenario: Admin exports filtered commissions CSV
- **WHEN** a verified admin requests commission CSV export for a date range
- **THEN** the system responds with a CSV download containing the filtered commission rows and finance columns

### Requirement: Admin can reverse commissions and post manual adjustments via API
The system SHALL expose verified-admin actions to reverse a `success` commission (required reason) and to post manual referral adjustments (signed amount, required reason) consistent with the referral-commission capability. Both actions MUST write audit metadata (actor, timestamp, reason).

#### Scenario: Admin API reverse requires reason
- **WHEN** a verified admin submits a reverse action without a reason
- **THEN** the system responds `422` and does not reverse the commission

#### Scenario: Admin API manual adjustment succeeds
- **WHEN** a verified admin posts a valid manual adjustment with amount and reason
- **THEN** the system responds success and persists the audited adjustment
