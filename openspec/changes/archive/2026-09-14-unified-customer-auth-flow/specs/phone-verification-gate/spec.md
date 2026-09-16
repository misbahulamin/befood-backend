## ADDED Requirements

### Requirement: Unified auth envelope includes phone_verification_required

The system SHALL include a boolean field `phone_verification_required` on every customer auth success response produced by the unified auth response builder (email login, phone OTP verify, Google OAuth, Facebook OAuth).

#### Scenario: Envelope field present on email login

- **WHEN** a customer successfully logs in with email and password
- **THEN** the response includes `token`, `user`, `customer_profile`, `auth_provider`, `phone_verification_required`, `onboarding_completion`, and `location_confirmation`

#### Scenario: Verified phone means not required

- **WHEN** the authenticated customer profile has `is_phone_verified=True`
- **THEN** `phone_verification_required` is `false`

#### Scenario: Unverified phone means required

- **WHEN** the authenticated customer profile has `is_phone_verified=False`
- **THEN** `phone_verification_required` is `true`

### Requirement: Social login signals phone verification without blocking login

The system SHALL allow Google and Facebook create-or-login to succeed and issue a session token even when the customer has no verified phone, and MUST set `phone_verification_required` accordingly so the client can start the phone OTP flow.

#### Scenario: New Google user without verified phone

- **WHEN** a valid Google credential creates a new customer without a verified phone
- **THEN** the system creates the customer and Google identity, returns an auth success envelope, and sets `phone_verification_required` to `true`

#### Scenario: Existing Google user with verified phone

- **WHEN** a valid Google credential matches an existing Google identity whose profile is phone-verified
- **THEN** the system logs the user in and sets `phone_verification_required` to `false`

#### Scenario: New Facebook user without verified phone

- **WHEN** a valid Facebook credential creates a new customer without a verified phone
- **THEN** the system creates the customer and Facebook identity, returns an auth success envelope, and sets `phone_verification_required` to `true`

#### Scenario: Existing Facebook user login

- **WHEN** a valid Facebook credential matches an existing Facebook identity
- **THEN** the system logs the user in and sets `phone_verification_required` from the profile’s phone verification state

### Requirement: Existing email users are not blocked for missing phone

The system MUST NOT reject email/password login solely because the customer lacks a verified phone. Existing users without phone MUST still receive a valid token, with `phone_verification_required` set to `true` when phone is not verified.

#### Scenario: Legacy email user without phone logs in

- **WHEN** an existing verified email customer without verified phone submits correct credentials
- **THEN** login succeeds with a token and `phone_verification_required` is `true`

### Requirement: Phone OTP success clears the gate

After successful phone OTP verification that establishes a verified phone on the customer, the auth success response MUST set `phone_verification_required` to `false`.

#### Scenario: New phone registration

- **WHEN** a new phone OTP verify creates User and CustomerProfile with `is_phone_verified=True`
- **THEN** the response sets `phone_verification_required` to `false`

#### Scenario: Existing phone login

- **WHEN** phone OTP verify logs in an existing phone-verified customer
- **THEN** the response sets `phone_verification_required` to `false`

### Requirement: Post-email-verification phone signal

When deferred email registration is finalized via email verification and the resulting customer has no verified phone, the verification success response MUST include `phone_verification_required: true` (additive; existing success messaging MUST remain).

#### Scenario: First-time email registration completes without phone

- **WHEN** email OTP/link verification creates the production customer and profile without a verified phone
- **THEN** the verification response indicates success and `phone_verification_required` is `true`

#### Scenario: Email verification does not revoke compatibility

- **WHEN** email verification succeeds
- **THEN** the response still includes the existing human-readable success message contract expected by current clients

### Requirement: Authenticated reads expose the same phone gate

Authenticated customer identity endpoints that already expose onboarding state (`/me` and equivalent profile reads) SHALL expose `phone_verification_required` using the same rule as the auth envelope.

#### Scenario: Me reflects phone gate

- **WHEN** an authenticated customer without verified phone calls `/me`
- **THEN** the response includes `phone_verification_required: true`

### Requirement: Onboarding phone completeness uses verification

For onboarding completion calculation, the system MUST treat phone as incomplete unless the customer profile has a verified phone (`is_phone_verified=True`).

#### Scenario: Unverified phone remains missing

- **WHEN** a profile has a phone value but `is_phone_verified=False`
- **THEN** onboarding `missing_fields` includes `phone`

### Requirement: No forced logout or token invalidation

Deploying this phone-gate contract MUST NOT invalidate existing AuthSession or legacy Token credentials and MUST NOT force-logout existing customers.

#### Scenario: Existing session remains valid after deploy semantics

- **WHEN** a customer already holds a valid auth token before the phone-gate fields are introduced
- **THEN** that token continues to authenticate until normal logout or security revoke events
