## ADDED Requirements

### Requirement: Password-reset email send helper
The system SHALL provide a service function that sends a customer password-reset email using the shared branded auth email templates. The email MUST include a primary CTA that opens a frontend reset URL derived from `FRONTEND_URL` (or equivalent setting) with opaque `uid` and `token` parameters. The plain-text part MUST include the same reset URL.

#### Scenario: Password-reset email contains reset link
- **WHEN** `send_password_reset_email` is invoked for a valid customer user
- **THEN** the system sends multipart email to that user’s address whose HTML and text include a password-reset URL with uid and token

#### Scenario: Unknown account does not leak existence on public request
- **WHEN** a client requests password reset for an email that does not exist
- **THEN** the public API response MUST NOT reveal whether the account exists (generic success message) and MUST NOT send mail to that address

### Requirement: Password-reset request endpoint
The system SHALL expose a customer password-reset request endpoint (e.g. `POST /user_management/password-reset/` or project-consistent path) that accepts `{ "email" }` and, when the account exists and is eligible, triggers the branded password-reset email. The endpoint MUST use anti-enumeration response semantics.

#### Scenario: Existing customer receives reset mail
- **WHEN** a client posts a registered customer email to the password-reset request endpoint
- **THEN** the system returns a generic success payload and sends one branded password-reset email

#### Scenario: Unregistered email still returns generic success
- **WHEN** a client posts an unknown email to the password-reset request endpoint
- **THEN** the system returns the same generic success shape without sending email

### Requirement: Reset token security
Password-reset tokens MUST be single-purpose reset tokens (Django `PasswordResetTokenGenerator` or equivalent), MUST NOT reuse the email-activation token generator hash rules incorrectly, and MUST expire according to Django/project password-reset timeout settings. Activation verify endpoints MUST NOT accept password-reset tokens as email verification.

#### Scenario: Activation verify rejects password-reset token
- **WHEN** a client presents a password-reset token to the email verification endpoint
- **THEN** verification fails and the account email-verified state is unchanged

### Requirement: Test send capability for branded auth emails
The system SHALL provide a developer/ops way (management command) to send a sample activation and/or password-reset branded email to a specified address for visual QA, including `misbahul.amin.ai@gmail.com`.

#### Scenario: Test command sends sample activation mail
- **WHEN** an operator runs the test-auth-email command with type activation and a destination address
- **THEN** the system sends one branded activation-sample email to that address using configured SMTP
