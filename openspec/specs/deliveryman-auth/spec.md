## Purpose

Delivery Man accounts can register, verify email, and log in only after admin approval, using `RiderProfile` and the `DELIVERY_MAN` group.

## Requirements

### Requirement: Delivery Man can register a new account
The system SHALL allow an unauthenticated client to register a Delivery Man account with email, password, first name, last name, phone, and address. The system MUST create an inactive Django `User`, a `RiderProfile` (Delivery Man profile) with `is_email_verified=False`, `approval_status=pending`, and `is_verified=False`, assign the user to the `DELIVERY_MAN` group, and send an email verification message. Duplicate email or phone MUST be rejected. The profile MUST expose a `public_id` (UUID) for later admin and authenticated identity use.

#### Scenario: Successful registration
- **WHEN** a client submits valid unique email, phone, password, name, and address to the Delivery Man registration endpoint
- **THEN** the system responds `201` with a success message and email, creates an inactive user with a `RiderProfile` pending email verification and admin approval, adds the `DELIVERY_MAN` group, and sends a verification email

#### Scenario: Duplicate email rejected
- **WHEN** a client registers with an email already used by any user
- **THEN** the system responds with a validation error and does not create a new Delivery Man account

#### Scenario: Duplicate phone rejected
- **WHEN** a client registers with a phone already used by another Delivery Man profile
- **THEN** the system responds with a validation error and does not create a new account

### Requirement: Delivery Man must verify email before admin review
The system SHALL provide a Delivery Man–specific email verification endpoint using a secure uid/token link. On successful verification the system MUST set `is_email_verified=True` and `email_verified_at`, and MUST NOT grant login access until admin approval (`is_active` remains false and `is_verified` remains false). Already-verified links MUST return a clear already-verified message. Invalid or expired tokens MUST be rejected.

#### Scenario: Successful email verification queues admin review
- **WHEN** a registered Delivery Man opens a valid verification link before expiry
- **THEN** the system marks the profile email as verified, keeps the account unapproved and inactive for login, and the account becomes eligible for the admin pending queue

#### Scenario: Invalid verification link
- **WHEN** a client uses an invalid or expired Delivery Man verification token
- **THEN** the system responds `400` with an invalid-or-expired message and does not change verification state

#### Scenario: Resend verification email
- **WHEN** an unverified Delivery Man requests resend verification for their email
- **THEN** the system sends a new verification email without revealing whether non-Delivery-Man emails exist beyond safe generic messaging consistent with customer resend behavior

### Requirement: Login requires email verification and admin approval
The system SHALL authenticate Delivery Man login with email and password and issue an auth token only when the user has a Delivery Man profile, the email is verified, and the admin has approved the account (`is_verified=True` and active). The system MUST NOT issue a token for pending or rejected accounts. When credentials are valid but admin approval is missing, the system MUST return a clear non-success response with the message: `Your information has not been approved by admin yet. Please wait until your account verification is completed.`

#### Scenario: Successful login after approval
- **WHEN** an approved, email-verified Delivery Man submits correct credentials
- **THEN** the system responds `200` with an auth token, user summary, groups, and Delivery Man profile summary including verified status

#### Scenario: Pending approval blocks login
- **WHEN** an email-verified but not yet approved Delivery Man submits correct credentials
- **THEN** the system does not issue a token and returns the dedicated pending-approval message

#### Scenario: Unverified email blocks login
- **WHEN** a registered Delivery Man who has not verified email submits correct credentials
- **THEN** the system does not issue a token and returns a message instructing them to verify email

#### Scenario: Invalid credentials
- **WHEN** a client submits an unknown email or wrong password to Delivery Man login
- **THEN** the system returns a generic invalid-credentials error without confirming which part failed

#### Scenario: Rejected account cannot login
- **WHEN** a rejected Delivery Man submits correct credentials
- **THEN** the system does not issue a token and returns the pending-approval (or equivalent not-approved) message without granting access

### Requirement: Authenticated Delivery Man can read own session profile
The system SHALL provide a `me` endpoint for an authenticated approved Delivery Man that returns user identity, groups, and profile fields needed by the client. Unauthenticated callers MUST receive `401`. Authenticated users without an approved Delivery Man profile MUST be denied.

#### Scenario: Approved delivery man reads me
- **WHEN** an authenticated approved Delivery Man calls the deliveryman `me` endpoint
- **THEN** the system responds `200` with that user’s identity and Delivery Man profile summary

#### Scenario: Unauthenticated me rejected
- **WHEN** an unauthenticated client calls the deliveryman `me` endpoint
- **THEN** the system responds `401 Unauthorized`
