## ADDED Requirements

### Requirement: Validate never creates referral relationships
`POST /referrals/validate/` SHALL only validate eligibility and record a `ReferralValidationEvent`. It MUST NOT create or update a `ReferralRelationship`, MUST NOT bind a customer identity, and MUST NOT require `X-Client-Type: mobile`.

#### Scenario: Successful validate leaves attribution empty
- **WHEN** an anonymous client validates a usable referral code
- **THEN** the response indicates valid and a validation event is stored with reason `OK`, and no `ReferralRelationship` exists for any new customer solely because of that call

### Requirement: Email finalize records structured attribution skip outcomes
When deferred email registration finalize attempts attribution and `attribute_on_signup` raises `ReferralError`, the system SHALL still complete account creation without a relationship (fail-closed), and MUST record a structured outcome including at least `customer_id`, the attempted `referral_code`, `client_type`, and machine-readable `error_code` (for example `REFERRER_INACTIVE`, `REFERRAL_MOBILE_ONLY`, `REFERRAL_SELF_NOT_ALLOWED`, `REFERRAL_ALREADY_ATTRIBUTED`). A vague log line without `error_code` is insufficient.

#### Scenario: Inactive referrer at finalize is observable
- **WHEN** pending registration has a referral code and the referrer has no active subscription at finalize
- **THEN** the customer account is created, no relationship is created, and the structured outcome includes `REFERRER_INACTIVE` (or the project’s equivalent inactive code)

### Requirement: Auth create success may expose referral attribution result
When a brand-new customer create path receives a non-empty `referral_code`, the success response SHALL include additive fields `referral_attributed` (boolean) and `referral_status_reason` (string or null). When attribution succeeds, `referral_attributed` MUST be true and `referral_status_reason` MUST be null or omitted. When attribution is skipped or fails closed, `referral_attributed` MUST be false and `referral_status_reason` MUST carry the machine-readable reason. When no referral code was supplied, these fields MAY be omitted.

#### Scenario: Phone new-customer attribution success
- **WHEN** anonymous phone OTP verify creates a new customer with a valid code and `X-Client-Type: mobile`
- **THEN** the success body includes `referral_attributed: true`

#### Scenario: Email finalize skip surfaces reason
- **WHEN** email finalize creates the account but attribution fails closed
- **THEN** the success body includes `referral_attributed: false` and a non-empty `referral_status_reason`
