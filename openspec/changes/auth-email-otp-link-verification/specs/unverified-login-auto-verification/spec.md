## ADDED Requirements

### Requirement: Correct-password unverified login triggers verification delivery with cooldown reuse
When a customer presents a correct email and password but the account email is not verified, the system SHALL refuse login with a clear message that the account is not verified yet. The system SHALL deliver dual-channel verification (OTP + link) only when allowed by OTP cooldown and hourly rules: if an active email-verification OTP already exists and was issued within the cooldown period, the system MUST reuse that OTP and MUST NOT send another email; otherwise it MAY issue a new OTP and send email when the hourly cap allows.

#### Scenario: First unverified login sends verification email
- **WHEN** an unverified customer posts valid credentials and no active verification OTP exists within the cooldown window
- **THEN** the response indicates the account is not verified (no auth token) and a verification email with OTP and link is sent (subject to hourly cap)

#### Scenario: Repeated unverified login within cooldown does not spam email
- **WHEN** an unverified customer posts valid credentials again while an active verification OTP was created within the cooldown period
- **THEN** the response still indicates the account is not verified and no new verification email is sent

#### Scenario: Wrong password does not send verification email
- **WHEN** a client posts incorrect credentials for any email
- **THEN** the system returns the existing invalid-credentials style error and does not send a verification email

#### Scenario: Already verified customer logs in normally
- **WHEN** a verified customer posts valid credentials
- **THEN** login succeeds with a DRF token as today and no verification email is sent for that attempt
