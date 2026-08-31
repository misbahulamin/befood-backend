## ADDED Requirements

### Requirement: Backend technical documentation for auth OTP
The system SHALL provide backend technical documentation at `user_management/docs/backend/email-verification-otp.md` covering OTP architecture, the `CustomerAuthOTP` model, purpose isolation, security rules (HMAC `code_hash` only — never plaintext in DB), expiry, attempt limits, resend cooldown, hourly issue cap, dual-channel email behavior, validate-otp vs confirm-otp semantics (confirm always re-verifies; validate does not authorize reset), and API contracts for email-verification and password-reset OTP. Cross-links from `docs/customer-auth-api.md` MUST be updated.

#### Scenario: Backend doc covers dual-channel flows and hash-only storage
- **WHEN** a backend developer reads the OTP backend documentation
- **THEN** they can follow registration/verify/resend and password-reset OTP flows including endpoints, payloads, errors, cooldown/rate limits, and the rule that only `code_hash` is stored

### Requirement: Frontend and mobile integration guide
The system SHALL provide a client integration guide at `user_management/docs/frontend-mobile/auth-verification-integration.md` covering React web and Android: registration verification (OTP screen + link/deep link), password reset (OTP + link), headers (`Content-Type`, optional `X-Client-Type`), request/response examples, error handling, example end-to-end sequences, cooldown/resend UX, and login not-verified behavior. The guide MUST state that OTP entry always supports manual typing and that platform autofill is optional. The guide MUST state that validate-otp success alone must not unlock password change; confirm-otp must send the OTP again for independent server verification.

#### Scenario: Web developer implements OTP verification with manual entry
- **WHEN** a React developer follows the integration guide
- **THEN** they can implement registration → manual OTP entry or link verification → login, including unverified-login messaging and cooldown-aware resend

#### Scenario: Android developer implements deep link and OTP reset
- **WHEN** an Android developer follows the integration guide
- **THEN** they can implement OTP screens (manual entry; optional autofill), deep-link handling, and password reset that calls confirm-otp with the OTP rather than trusting validate-otp alone
