## ADDED Requirements

### Requirement: Referral applies only on first customer creation
The system SHALL accept and attribute a referral code only when creating a brand-new customer (`CustomerProfile` that did not previously exist). Login, phone bind, email verify of an existing account, social login of an existing account, and attaching a second identifier MUST NOT create a new `ReferralRelationship`.

#### Scenario: New mobile customer with valid code
- **WHEN** a previously unknown identifier completes mobile registration with a valid usable referral code
- **THEN** the system creates at most one immutable `ReferralRelationship` for that new customer

#### Scenario: Existing phone login ignores referral
- **WHEN** a client supplies a referral code during phone OTP verify for a phone that already belongs to a customer
- **THEN** the system logs the customer in without creating or changing referral attribution

#### Scenario: Phone bind never attributes referral
- **WHEN** an authenticated customer binds a phone and a referral code is present in the request
- **THEN** the system ignores or rejects the referral code and does not create a `ReferralRelationship`

### Requirement: A customer never receives a second referral attribution
Once a customer has been attributed to a referrer, or once the customer account already exists without needing new-customer creation, the system MUST reject attempts to apply another referral code for that customer (`REFERRAL_ALREADY_ATTRIBUTED` or equivalent). Creating a second customer account for the same human to re-use referral MUST be prevented by identity-linking rules elsewhere in this change.

#### Scenario: Second attribution attempt on same profile
- **WHEN** a customer who already has a `ReferralRelationship` attempts to apply another referral code
- **THEN** the system rejects the change and keeps the original relationship

#### Scenario: Existing account registration path cannot re-open referral
- **WHEN** an identifier already maps to an existing customer
- **THEN** server-side attribution MUST NOT run for that request even if the client sends `referral_code`

### Requirement: Referral UI eligibility is server-backed for new identifiers only
Backend pre-check endpoints used by clients (email-check and phone availability/existence) MUST expose enough signal for clients to know whether the identifier is new vs existing, so referral input is shown only for new-customer flows. Backend remains authoritative: hiding UI is not sufficient without server-side guards above.

#### Scenario: Existing email check does not imply new referral
- **WHEN** email-check reports an existing verified customer
- **THEN** clients MUST treat the flow as login (no referral attribution path), and the server MUST not attribute referral on subsequent login

#### Scenario: Unknown phone allows new-customer referral path
- **WHEN** phone availability/existence indicates the phone is not registered
- **THEN** clients MAY show referral input for the subsequent anonymous create-or-register phone verify, subject to mobile-only attribution rules
