## ADDED Requirements

### Requirement: Customer registration accepts email and password only
The system SHALL allow a new customer to start registration via `POST /user_management/customer/register/` with only `email` and `password` in the request body. The endpoint MUST NOT require `first_name`, `last_name`, `phone`, `occupation`, or `is_bachelor` at registration time. Password MUST pass existing Django password validators. Email MUST be normalized to lowercase and MUST be unique (case-insensitive).

#### Scenario: Minimal registration succeeds
- **WHEN** a client posts `{ "email": "new@example.com", "password": "ValidPass123!" }` with no profile fields
- **THEN** the system returns `201 Created` with `{ "message", "email" }`, creates an inactive `User` and `CustomerProfile` with null/empty onboarding fields, assigns the `CUSTOMER` group, and sends the existing activation email

#### Scenario: Duplicate email rejected
- **WHEN** a client registers with an email that already exists (any case)
- **THEN** the system returns `400` with a field validation error on `email`

#### Scenario: Invalid password rejected
- **WHEN** a client registers with a password that fails Django validators
- **THEN** the system returns `400` with a validation error on `password` and does not create a user

### Requirement: Legacy registration fields are not required at signup
During a documented compatibility window, the system MAY accept legacy registration fields (`first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`) if present but MUST NOT require them. Unknown or privileged fields MUST be ignored or rejected per project serializer allow-list policy.

#### Scenario: Legacy client sends extra fields without blocking
- **WHEN** an older client posts email, password, and optional legacy profile fields
- **THEN** the system completes registration without requiring all legacy fields and persists any valid optional legacy values supplied

#### Scenario: Unknown fields rejected or stripped
- **WHEN** a client posts unsupported fields such as `is_email_verified` or `role` at registration
- **THEN** the system does not apply those values to the created account

### Requirement: Existing email verification is reused unchanged
Customer registration MUST trigger the existing `send_activation_email` flow using `EmailVerificationTokenGenerator`. Verification MUST continue via `GET /user_management/verify-email/<uidb64>/<token>/` with existing 24-hour token expiry. Resend MUST continue via `POST /user_management/resend-verification/` with existing anti-enumeration behavior. No parallel verification mechanism SHALL be introduced.

#### Scenario: Verification email sent on registration
- **WHEN** a customer completes minimal registration
- **THEN** the system sends one activation email using the existing templates and token generator

#### Scenario: Successful verification activates account
- **WHEN** a customer clicks a valid, unexpired verification link
- **THEN** the system sets `CustomerProfile.is_email_verified=True`, records `email_verified_at`, sets `User.is_active=True`, and returns the existing success response

#### Scenario: Resend preserves security semantics
- **WHEN** a client requests resend for an unknown email
- **THEN** the system returns the existing generic success message without revealing account existence

### Requirement: Email verification completes account registration
Account registration complete SHALL be defined as successful email verification. A verified customer MUST be eligible for normal login even when onboarding profile fields (`first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`) are still missing. Profile incomplete MUST NOT block login unless an unrelated existing business rule applies.

#### Scenario: Login allowed with incomplete onboarding profile
- **WHEN** a verified customer with null phone and empty name attempts login with valid credentials
- **THEN** the system returns `200` with token and user payload

#### Scenario: Unverified customer cannot login
- **WHEN** a customer registered but not yet verified attempts login
- **THEN** the system returns `400` with the existing verify-email message

### Requirement: Non-customer registration flows are unchanged
This change MUST NOT alter admin, deliveryman, staff, or internal user registration or login endpoints, serializers, or permission gates.

#### Scenario: Deliveryman registration unaffected
- **WHEN** a deliveryman registers through the existing deliveryman registration endpoint
- **THEN** behavior remains identical to pre-change requirements

#### Scenario: Admin login unaffected
- **WHEN** an admin logs in through `/user_management/admin/login/`
- **THEN** existing admin verification gates still apply
