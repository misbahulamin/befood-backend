## ADDED Requirements

### Requirement: Customer can retrieve own referral code link and eligibility
The system SHALL provide an authenticated customer endpoint that returns the caller’s referral `code`, shareable referral link, whether the code is currently usable (active meal subscription), and summary statistics including referred-user count, lifetime commission earned, and current-month commission earned. The endpoint MUST NOT expose another customer’s code or earnings.

#### Scenario: Active subscriber views referral me payload
- **WHEN** an authenticated customer with an active subscription requests their referral profile
- **THEN** the system responds `200` with code, link, `is_usable=true`, and summary stats

#### Scenario: Inactive subscriber sees unusable code
- **WHEN** an authenticated customer without an active subscription requests their referral profile
- **THEN** the system responds `200` with the same permanent code, `is_usable=false`, and does not invent a new code

### Requirement: Customer can list referred users and commission history
The system SHALL provide paginated authenticated endpoints for the caller’s referred users and commission history. Referred-user items MUST include referred identity suitable for the client (public id and safe display fields), attribution date, and commission totals generated from that user. Commission history items MUST include commission public id, referred user, meal identifiers/date, meal price, percentage, amount, status, and created timestamp. Results MUST be scoped to the caller as referrer only.

#### Scenario: Referrer lists referred users
- **WHEN** a referrer with three attributed users requests the referred-users list
- **THEN** the system responds `200` with a paginated list of those three relationships only

#### Scenario: Referrer lists commission history
- **WHEN** a referrer with prior completed commissions requests commission history
- **THEN** the system responds `200` with paginated commission rows ordered newest first

### Requirement: Clients can validate a referral code before registration with abuse protection
The system SHALL provide a validation endpoint that accepts a referral code and returns whether it is usable for mobile registration. Invalid codes MUST return a clear error. Codes belonging to referrers without an active meal subscription MUST return the inactive-referrer message. The endpoint MUST be rate-limited for public or pre-auth use, including **IP-based throttling**. Successful and failed validations MUST be countable for admin conversion analytics (event table or equivalent). Device-based throttling MAY be added later and is not required for v1.

#### Scenario: Valid code validation succeeds
- **WHEN** a mobile client validates an existing code owned by an active subscriber
- **THEN** the system responds success indicating the code may be used and records a validation event

#### Scenario: Missing code validation fails
- **WHEN** a client validates a non-existent referral code
- **THEN** the system responds with a client error and does not attribute anyone

#### Scenario: Excessive validate requests from one IP are throttled
- **WHEN** a client exceeds the configured validate rate limit for its IP
- **THEN** the system responds `429 Too Many Requests` and does not perform unlimited validations
