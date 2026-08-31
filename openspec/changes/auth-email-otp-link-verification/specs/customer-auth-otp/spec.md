## ADDED Requirements

### Requirement: Purpose-isolated hashed customer auth OTPs
The system SHALL store customer one-time passwords in a purpose-scoped persistence model (email verification vs password reset) with hashed codes (`code_hash` via HMAC-SHA256), absolute expiry, consumption timestamp, and failed-attempt counting. Plaintext OTP values MUST NEVER be persisted in the database. Verification OTPs MUST NOT be accepted for password reset, and password-reset OTPs MUST NOT be accepted for email verification.

#### Scenario: Issue replaces prior active OTP for same purpose
- **WHEN** a new OTP is issued for a customer and purpose that already has an unconsumed OTP and cooldown/hourly limits allow issuance
- **THEN** previous unconsumed OTPs for that user and purpose become unusable and only the newly issued code can succeed within its expiry window

#### Scenario: Wrong purpose is rejected
- **WHEN** a client submits a valid password-reset OTP to an email-verification endpoint (or the reverse)
- **THEN** the system rejects the attempt as invalid without verifying the unrelated purpose

#### Scenario: Expired or exhausted OTP is rejected
- **WHEN** a client submits an OTP after `expires_at` or after the maximum failed attempts
- **THEN** the system rejects the attempt and does not mark the account verified or change the password

#### Scenario: Database stores only code_hash
- **WHEN** an OTP is issued
- **THEN** the persisted row contains `code_hash` and MUST NOT contain the plaintext six-digit code

### Requirement: OTP resend cooldown and hourly issue cap
The system SHALL enforce a configurable minimum interval between OTP generations for the same user and purpose (default 60 seconds) and a configurable maximum number of OTP issues per user per purpose per rolling hour. During cooldown, the system MUST NOT generate a new OTP or send a duplicate email for that purpose when an active OTP already exists.

#### Scenario: Resend within cooldown reuses active OTP
- **WHEN** a client requests another verification or password-reset OTP while an active OTP for that purpose was created within the cooldown window
- **THEN** the system does not issue a new code, does not send another email, and returns the usual success or anti-enumeration style response appropriate to the endpoint

#### Scenario: Hourly issue cap blocks further generation
- **WHEN** a user has already reached the configured maximum OTP issues for a purpose in the last hour and cooldown has elapsed
- **THEN** the system refuses to generate another OTP for that purpose until the rolling window allows it

### Requirement: Dual-channel email verification (OTP and link)
The system SHALL continue to support existing link-based email verification and SHALL additionally support verifying a customer email with a 6-digit OTP. Registration and eligible resend flows MUST deliver both a verification deep link and a fresh OTP in the branded activation email (subject to cooldown and hourly caps on subsequent sends).

#### Scenario: Register sends OTP and link
- **WHEN** a customer successfully registers
- **THEN** the activation email includes a usable verification link and a 6-digit OTP bound to purpose `email_verification`

#### Scenario: Verify with correct OTP
- **WHEN** an unverified customer posts a valid unexpired OTP for their email to the email-verification OTP endpoint
- **THEN** the system marks the profile email verified, activates the user as today, consumes the OTP, and returns a success message

#### Scenario: Verify with wrong OTP
- **WHEN** a client posts an incorrect OTP for an existing unverified customer
- **THEN** the system increments attempt count and returns an invalid/expired-style error without verifying the account

#### Scenario: Existing link verification still works
- **WHEN** a client uses a valid uidb64 and `EmailVerificationTokenGenerator` token on the existing verify-email link endpoint
- **THEN** the account is verified as before and password-reset tokens remain unusable for this endpoint

### Requirement: Email verification OTP APIs are public
The system SHALL expose public JSON endpoints to verify email by OTP and to resend verification OTP (including an OTP-named resend alias that shares behavior with resend-verification). These endpoints MUST NOT require authentication. Unknown emails on resend MUST use anti-enumeration messaging consistent with existing resend behavior. Resend MUST apply cooldown and hourly caps.

#### Scenario: Resend for unverified customer after cooldown
- **WHEN** an unverified customer requests resend via either resend-verification or verify-email resend-otp and cooldown and hourly caps allow a new issue
- **THEN** the system issues a new OTP, invalidates the prior verification OTP, and sends a branded email with OTP and link

#### Scenario: Resend for unknown email
- **WHEN** a client requests resend for an email with no customer account
- **THEN** the system returns a generic success-style message and does not reveal whether the account exists

### Requirement: Dual-channel password reset (OTP and link)
The system SHALL keep existing password-reset request, uid+token validate, and uid+token confirm endpoints working, and SHALL send both a reset deep link and a fresh password-reset OTP in the branded reset email when issuance is allowed. The system SHALL expose public OTP validate and OTP confirm endpoints. Successful OTP confirm MUST independently re-verify the OTP (hash, expiry, attempts, purpose), apply Django password validation, set the new password, consume the OTP, and delete all DRF auth tokens for that user. A prior successful validate-otp MUST NOT be required and MUST NOT alone authorize password change.

#### Scenario: Request reset sends OTP and link
- **WHEN** a customer account exists and password reset is requested (including the request-otp alias) and cooldown/hourly limits allow
- **THEN** the email includes a reset link and a 6-digit OTP for purpose `password_reset`, and the HTTP response remains the generic anti-enumeration message

#### Scenario: Validate OTP without consuming and without granting reset authority
- **WHEN** a client posts a correct unexpired password-reset OTP to validate-otp
- **THEN** the system returns success, leaves the OTP unconsumed, and does not grant any server-side password-reset session or capability beyond that UX check

#### Scenario: Confirm password with OTP re-verifies independently
- **WHEN** a client posts confirm-otp with email, otp, new_password, and confirm_password whether or not validate-otp was called earlier
- **THEN** the system independently verifies the OTP again, updates the password on success, deletes DRF tokens, consumes the OTP, and returns success without issuing a new auth token

#### Scenario: Reject reused OTP after confirm
- **WHEN** a client retries confirm-otp with an OTP that was already consumed
- **THEN** the system rejects the request and does not change the password again

#### Scenario: Existing link reset still works
- **WHEN** a client uses existing password-reset validate/confirm with valid uid and `PasswordResetTokenGenerator` token
- **THEN** password reset succeeds as today and activation tokens remain unusable for reset
