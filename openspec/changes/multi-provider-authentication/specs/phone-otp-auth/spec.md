## ADDED Requirements

### Requirement: Normalize Bangladesh phone numbers centrally
The system SHALL expose and use a centralized `normalize_phone_number()` helper for all phone OTP, linking, and customer phone identity operations. Inputs `01712345678`, `+8801712345678`, and `8801712345678` (and equivalent spaced/dashed forms when accepted) MUST normalize to the same canonical Bangladesh local form (`01XXXXXXXXX`). Invalid numbers MUST be rejected before OTP issuance.

#### Scenario: Equivalent formats map to one canonical phone
- **WHEN** clients submit `01712345678`, `+8801712345678`, and `8801712345678` through OTP send
- **THEN** the system stores and rate-limits against the same canonical phone key and does not treat them as different users

#### Scenario: Invalid phone rejected
- **WHEN** a client submits a phone that cannot be normalized to a valid BD mobile number
- **THEN** the system rejects the request with a validation error and does not send SMS

### Requirement: Send phone OTP via SMS.NET.BD
The system SHALL provide an unauthenticated endpoint that accepts a phone number, normalizes it, generates a one-time password, stores only a cryptographic hash of the OTP with expiry and attempt metadata, and sends the plaintext OTP exclusively through the configured SMS.NET.BD send API. Plaintext OTP MUST NOT be persisted in the database.

#### Scenario: Successful OTP send
- **WHEN** a client submits a valid phone number that is eligible for OTP issuance and SMS credentials are configured
- **THEN** the system stores a hashed OTP keyed by the canonical phone, calls SMS.NET.BD, and returns a success response that does not include the OTP code

#### Scenario: SMS provider failure
- **WHEN** SMS.NET.BD returns a failure or is unreachable after OTP generation is attempted
- **THEN** the system returns a clear non-success error suitable for clients and does not leave a usable unverifiable auth session

### Requirement: Enforce OTP rate limits and resend cooldown
The system SHALL enforce configurable OTP resend cooldown, maximum verification attempts per issued code, TTL expiry, and maximum OTP issues per canonical phone (and SHOULD apply IP-based throttling) consistent with project `AUTH_OTP_*` style settings for phone OTP.

#### Scenario: Resend blocked by cooldown
- **WHEN** a client requests another OTP for the same canonical phone before the resend cooldown elapses
- **THEN** the system rejects the request without sending a new SMS

#### Scenario: Hourly issue cap reached
- **WHEN** a canonical phone has already reached the maximum OTP issues in the rolling hour window
- **THEN** the system rejects further OTP send requests until the window allows

### Requirement: Verify phone OTP and create or login customer
The system SHALL verify a submitted OTP against the stored hash for the normalized phone, TTL, and attempt limits. On success for an existing customer with that phone, the system MUST log the user in. On success for a new phone, the system MUST create a customer `User` with `set_unusable_password()`, a `CustomerProfile` with `is_phone_verified=True` and only phone required, `profile_completed` reflecting incomplete profile when name/email are absent, assign the `CUSTOMER` group, and return the unified auth success response.

#### Scenario: Existing user phone login
- **WHEN** a client submits a correct unexpired OTP for a phone that already belongs to a customer (any accepted input format)
- **THEN** the system issues an auth session token for that customer, marks the OTP consumed, and returns the unified auth envelope

#### Scenario: New phone-only account creation
- **WHEN** a client submits a correct unexpired OTP for a phone with no existing customer
- **THEN** the system creates a password-less customer with verified phone only, leaves name/email for later profile completion, sets `profile_completed` accordingly, and returns the unified auth envelope

#### Scenario: Wrong OTP increments attempts
- **WHEN** a client submits an incorrect OTP while attempts remain
- **THEN** the system rejects the verification, increments the attempt counter, and does not issue a token

#### Scenario: Expired OTP rejected
- **WHEN** a client submits a previously valid OTP after its expiry time
- **THEN** the system rejects the verification and does not issue a token
