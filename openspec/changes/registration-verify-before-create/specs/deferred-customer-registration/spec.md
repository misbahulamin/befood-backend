## ADDED Requirements

### Requirement: Signup stores pending registration only
The system SHALL NOT create a permanent customer `User` or `CustomerProfile` when a customer submits registration. The system SHALL persist a temporary pending registration record containing the normalized email, password hash, and any accepted optional profile fields from the existing registration contract. The register endpoint response SHALL remain unauthenticated (no auth token) and SHALL instruct the client that verification is required.

#### Scenario: Successful register creates pending row only
- **WHEN** a client posts a valid customer registration for an email that is not owned by an active verified customer
- **THEN** the system upserts a pending registration for that email, does not create an active customer account, sends a verification email when OTP issuance allows, and returns a success-style response with the email

#### Scenario: Register rejects email already verified
- **WHEN** a client registers with an email that already belongs to an active email-verified customer
- **THEN** the system rejects the request without creating another pending registration for that email

#### Scenario: Re-register while pending updates the pending record
- **WHEN** a client registers again with an email that already has a non-expired pending registration
- **THEN** the system updates the pending registration (including password hash as applicable), does not create a permanent user, and applies existing OTP cooldown/hourly rules before sending another email

### Requirement: Account is created only after successful email verification
The system SHALL create the customer `User` (active) and `CustomerProfile` (email verified) only after a successful email verification via OTP or verification link for a valid pending registration. After successful creation the pending registration SHALL be consumed or deleted so the same pending secret cannot create a second account.

#### Scenario: OTP verification creates the account
- **WHEN** a client posts a correct unexpired email-verification OTP for an email with a valid pending registration
- **THEN** the system creates the customer user and profile as active and verified, consumes the pending registration and OTP, and returns a success message that the user may log in

#### Scenario: Link verification creates the account
- **WHEN** a client opens a valid pending-scoped verification link for a non-expired pending registration
- **THEN** the system creates the customer user and profile as active and verified and invalidates that pending registration

#### Scenario: Invalid OTP does not create an account
- **WHEN** a client posts an incorrect or expired OTP for a pending registration email
- **THEN** the system does not create a `User`, increments attempt handling per OTP rules, and returns an invalid/expired-style error

### Requirement: Resend verification targets pending registrations
The system SHALL allow public resend of verification email for emails that have a valid pending registration, subject to the same cooldown and hourly issuance caps used for auth OTPs. Resend for unknown or expired pending emails SHALL use anti-enumeration messaging and MUST NOT create a permanent user.

#### Scenario: Resend for pending email after cooldown
- **WHEN** a client requests resend for an email with a valid pending registration and cooldown/hourly caps allow a new issue
- **THEN** the system issues a new verification secret/OTP, sends the activation email, and still does not create a permanent user until verify succeeds

#### Scenario: Resend for unknown email
- **WHEN** a client requests resend for an email with no pending registration and no unverified legacy account in the compatibility path
- **THEN** the system returns a generic success-style message without revealing whether a registration exists

### Requirement: Pending registrations expire and can be cleaned up
The system SHALL expire pending registrations so abandoned or wrong-email signups do not remain indefinitely. The system SHALL provide an operable cleanup path (management command and/or documented job) that deletes expired pending rows without affecting verified customer accounts.

#### Scenario: Expired pending cannot verify
- **WHEN** a client attempts OTP or link verification after the pending registration has expired
- **THEN** the system rejects verification and does not create a customer account

#### Scenario: Cleanup removes expired pending only
- **WHEN** the cleanup job runs
- **THEN** expired pending registrations are removed and verified customer users remain untouched

### Requirement: Login requires a real verified account
The system SHALL allow customer login only for existing verified/active customer accounts. An email that only has a pending registration (never verified) MUST NOT authenticate as a user.

#### Scenario: Login with pending-only email fails
- **WHEN** a client attempts login with an email that has a pending registration but no customer `User`
- **THEN** the system rejects authentication with the normal invalid-credentials style response and does not issue an auth token

#### Scenario: Login after successful verify succeeds
- **WHEN** a customer completes verification (account created) and then posts valid credentials to login
- **THEN** the system authenticates the user as today
