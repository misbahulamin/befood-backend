## ADDED Requirements

### Requirement: Single customer identity for email and phone
The system SHALL treat a BeFood customer as one `User` + one `CustomerProfile`. A login or verification using an email that already belongs to a customer, or a phone that already belongs to a customer, MUST resolve to that same pair. The system MUST NOT create a second `User` or `CustomerProfile` when either identifier already maps to an existing customer.

#### Scenario: Login with email after phone was bound
- **WHEN** a customer has both `User.email` and verified `CustomerProfile.phone` set
- **THEN** authenticating with that email returns the same customer as authenticating with that phone

#### Scenario: Login with phone after email registration and bind
- **WHEN** a customer registered with email, then successfully bound a phone via authenticated bind OTP
- **THEN** phone OTP login for that phone returns the same `User` and `CustomerProfile` as the email account

### Requirement: Authenticated phone bind updates the same profile
When an authenticated customer verifies a phone that is not owned by another customer, the system SHALL update that customer’s `CustomerProfile.phone` (and phone verification flags) on the existing profile. The system MUST NOT create a new `User`, `CustomerProfile`, or `ReferralProfile` during bind.

#### Scenario: Email account binds first phone
- **WHEN** an authenticated customer with `phone` null completes bind OTP for a free phone number
- **THEN** the same `CustomerProfile` stores the normalized phone as verified and no new user row is created

#### Scenario: Bind rejects phone owned by another customer
- **WHEN** an authenticated customer attempts to bind a phone already linked to a different customer
- **THEN** the system rejects the operation with a phone conflict error and leaves both accounts unchanged

### Requirement: Anonymous phone OTP creates only when phone is unknown
Unauthenticated phone OTP verify MUST look up `CustomerProfile` by normalized phone. If found, it MUST log into that customer and MUST NOT run new-customer creation or referral attribution. If not found, it MAY create a phone-only customer. If the request is authenticated as a customer, the system MUST NOT create a new customer via the anonymous create path (it MUST bind or reject with a clear code directing clients to the bind endpoints).

#### Scenario: Existing phone logs in without creation
- **WHEN** an unauthenticated client verifies OTP for a phone already on a `CustomerProfile`
- **THEN** the system returns that customer’s auth session and does not create a new profile

#### Scenario: Unknown phone creates once
- **WHEN** an unauthenticated client verifies OTP for a phone that matches no `CustomerProfile`
- **THEN** the system creates exactly one phone-only customer and may accept referral only for that new customer

#### Scenario: Authenticated client cannot create a second account via anonymous verify
- **WHEN** an authenticated customer calls the anonymous phone OTP verify endpoint with a phone not yet on their profile
- **THEN** the system either binds the phone to the authenticated profile or rejects with a stable error code instructing use of bind endpoints, and MUST NOT create a second customer

### Requirement: No automatic production account merge
The system MUST NOT automatically merge distinct existing `User`/`CustomerProfile` rows, rewrite customer IDs, or mutate historical wallet, subscription, meal, or referral rows as part of identity linking. Duplicate handling for already-split accounts MUST be detect-and-report (and optional manual ops process) only.

#### Scenario: Detection does not mutate data
- **WHEN** operators run the duplicate-identity detection command
- **THEN** the command reports candidate issues without merging accounts or altering referral history
