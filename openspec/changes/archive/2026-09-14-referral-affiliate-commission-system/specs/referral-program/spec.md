## ADDED Requirements

### Requirement: Every customer has a permanent unique referral code
The system SHALL ensure each `CustomerProfile` has exactly one `ReferralProfile` with a globally unique referral `code`. The code MUST use the format `BEF` followed by exactly eight uppercase alphanumeric characters (example `BEF8A92KX`). The code MUST be generated automatically at customer account creation and MUST remain permanently associated with that customer. Existing customers without a code MUST receive one via backfill. Duplicate codes MUST be rejected by the database uniqueness constraint.

#### Scenario: New customer receives a unique BEF+8 code
- **WHEN** a new `CustomerProfile` is created
- **THEN** the system creates a `ReferralProfile` whose code matches `BEF` plus eight alphanumeric characters and is unique

#### Scenario: Code collides during generation
- **WHEN** generated code already exists
- **THEN** the system retries with a new code until insert succeeds under the unique constraint

### Requirement: Referral code usability depends on active meal subscription
The system SHALL treat a referral code as usable for new attributions only when the referrer has an active `CustomerSubscription` (`status=active`). When the referrer has no active subscription, validation and attribution MUST fail with the client-facing detail containing `Your referrer does not have an active meal subscription.` When the referrer later regains an active subscription, the same code MUST become usable again without regenerating the code.

#### Scenario: Active subscriber code is usable
- **WHEN** a client validates a referral code whose owner has an active meal subscription
- **THEN** the system responds that the code is valid

#### Scenario: Inactive referrer code is rejected
- **WHEN** a client validates or applies a referral code whose owner has no active meal subscription
- **THEN** the system rejects the operation with a message including `Your referrer does not have an active meal subscription.`

### Requirement: Referral attribution is mobile-only and immutable
The system SHALL create at most one `ReferralRelationship` per referred customer, linking them to exactly one referrer. Attribution MUST only succeed when the registration client is mobile (`X-Client-Type: mobile` or equivalent mobile registration channel). Web registration that includes a referral code MUST be rejected with `422`. After a relationship exists, the referred customer MUST NOT be able to change referrer. Self-referral MUST be rejected.

#### Scenario: Mobile signup with valid code creates relationship
- **WHEN** a new customer completes mobile registration with a valid usable referral code
- **THEN** the system stores an immutable relationship from referrer to referred and records the code used and attribution timestamp

#### Scenario: Web signup with referral code is rejected
- **WHEN** a web client submits a referral code during registration
- **THEN** the system responds `422` and does not create a referral relationship

#### Scenario: Second referral attempt is rejected
- **WHEN** a customer who already has a referrer attempts to apply another referral code
- **THEN** the system rejects the change and keeps the original relationship

#### Scenario: Self-referral is rejected
- **WHEN** a customer attempts to attribute using their own referral code
- **THEN** the system rejects the operation without creating a relationship

### Requirement: One referrer may attribute many referred users
The system SHALL allow a single eligible referrer to be linked to many referred customers. Each referred customer MUST still have at most one referrer.

#### Scenario: Referrer invites multiple users
- **WHEN** an active subscriber’s code is used successfully by three distinct new mobile customers
- **THEN** the system stores three relationships all pointing to that referrer

### Requirement: Pending email registration stores referral intent snapshot
For mobile email pending registration, the system SHALL store the submitted `referral_code`, a `referrer_snapshot_id` resolved at submit time when the code is resolvable, and preserve intent timing. Final attribution MUST re-check referrer active-subscription eligibility at finalize time. The snapshot MUST NOT force attribution if the referrer is inactive at finalize.

#### Scenario: Referrer becomes inactive before email finalize
- **WHEN** a pending registration stored a referral code for an then-active referrer and the referrer has no active subscription at finalize
- **THEN** the system rejects attribution with the inactive-referrer message and still may complete account creation without a referral relationship per auth rules

#### Scenario: Referrer still active at finalize
- **WHEN** pending registration includes a valid referral snapshot and the referrer remains active at finalize
- **THEN** the system creates the immutable referral relationship

### Requirement: ReferralProfile may track share analytics fields
The system SHALL allow `ReferralProfile` to store optional `share_count` and `last_shared_at` for marketing analytics. These fields MUST default to zero/null and MUST NOT affect commission eligibility.

#### Scenario: Share counters default safely
- **WHEN** a referral profile is created
- **THEN** `share_count` is `0` and `last_shared_at` is null until a share event is recorded

### Requirement: Referral query indexes support admin and customer lists
The system SHALL create database indexes sufficient for referrer/referred lookups and time-ordered commission and relationship lists, including at least: `ReferralCommission(referrer_id, created_at)`, `ReferralCommission(referred_id)`, `ReferralCommission(order_delivery_id)`, `ReferralCommission(status)`, `ReferralRelationship(referrer_id)`, unique `ReferralRelationship(referred_id)`, and `ReferralRelationship` attribution/created timestamp.

#### Scenario: Schema includes required referral indexes
- **WHEN** referral migrations are applied
- **THEN** the listed indexes/constraints exist on the referral tables
