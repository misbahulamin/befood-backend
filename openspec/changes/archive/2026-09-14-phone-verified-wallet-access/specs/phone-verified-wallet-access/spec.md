## ADDED Requirements

### Requirement: Phone-verified customers can access wallet funding without email
The system SHALL allow an authenticated customer whose identity is verified via phone OTP (`CustomerProfile.is_phone_verified=True`) to access customer wallet endpoints—including balance, transaction history, manual recharge submit, and manual withdraw submit—without requiring `is_email_verified=True` or a non-empty email. Email verification MUST remain optional for phone-registered accounts. The same identity helper used for other customer features (`is_customer_identity_verified` / equivalent) MUST treat phone verification as sufficient trust.

#### Scenario: Phone-only customer submits recharge successfully past identity gate
- **WHEN** an authenticated CUSTOMER with blank or unverified email, `is_phone_verified=True`, and an otherwise valid recharge payload (amount, payment method, transaction id) posts to the customer recharge endpoint
- **THEN** the system MUST NOT reject the request for missing email verification, and MUST proceed under the existing manual funding rules (pending create, validation, freeze, kill-switch, etc.)

#### Scenario: Phone-only customer can read wallet balance
- **WHEN** an authenticated CUSTOMER with `is_phone_verified=True` and without email verification requests their wallet summary
- **THEN** the system responds successfully with that customer’s wallet (creating a zero-balance wallet if none exists) and MUST NOT require email verification

#### Scenario: Unverified identity still blocked from recharge
- **WHEN** an authenticated CUSTOMER with `is_email_verified=False`, `is_phone_verified=False`, and no trusted social identity posts a recharge
- **THEN** the system responds `403` with an identity-verification-required error and does not create a funding request

### Requirement: Wallet identity denial uses wallet-appropriate messaging
When a customer wallet endpoint denies access solely because identity is not verified, the system SHALL return `403` with English detail that refers to identity verification for wallet use (for example recharge/wallet access), and MUST NOT require clients to interpret order-placement wording as the wallet failure reason. Email-specific wording (“email verification is required”) MUST NOT be used for this denial.

#### Scenario: Identity denial on recharge is not email-only copy
- **WHEN** an identity-unverified authenticated customer posts recharge
- **THEN** the `403` detail indicates identity verification is required for wallet/recharge and does not state that email verification alone is required

### Requirement: Mobile clients treat phone identity as sufficient for recharge UX
Client documentation for this capability SHALL state that mobile apps MUST NOT hard-block wallet recharge solely because email is missing or unverified when `verification_status.identity_verified` is true or `phone_verified` is true. Optional email collection MAY be prompted as soft UX only. If the app currently gates recharge on email verification, that gate MUST be removed or replaced with the identity rule after backend deploy.

#### Scenario: Documented mobile gate rule
- **WHEN** a phone-verified customer’s auth or `/me` payload shows `phone_verified=true` (and thus `identity_verified=true`) with email unverified
- **THEN** documented mobile behavior allows opening and submitting the recharge flow without requiring an email verification step first
