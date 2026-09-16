## ADDED Requirements

### Requirement: Password-reset request endpoint (customer)
The system SHALL expose `POST /user_management/password-reset/` that accepts `{ "email" }` for customer accounts. When a matching user with a `customer_profile` exists, the system MUST send one branded password-reset email using the existing `PasswordResetTokenGenerator` and frontend deep link. The endpoint MUST return the same generic success message whether or not the account exists (anti-enumeration). The endpoint MUST be public (`AllowAny`).

#### Scenario: Existing customer email triggers mail
- **WHEN** a client posts a registered customer email to the password-reset request endpoint
- **THEN** the system returns HTTP 200 with the generic success message and sends one password-reset email

#### Scenario: Unknown email is anti-enumeration
- **WHEN** a client posts an email that does not match a customer account
- **THEN** the system returns HTTP 200 with the same generic success message and does not send email

### Requirement: Password-reset token validate endpoint
The system SHALL expose `POST /user_management/password-reset/validate/` that accepts `{ "uid", "token" }` (where `uid` is the uidb64 value from the email link). The endpoint MUST be public. When the uid resolves to a customer user and the reset token is valid and unexpired, the system MUST return HTTP 200 indicating the token is valid. When the uid/token is invalid, expired, malformed, or not a customer, the system MUST return HTTP 400 without setting a password.

#### Scenario: Valid reset token
- **WHEN** a client posts a valid customer `uid` and password-reset `token`
- **THEN** the system returns HTTP 200 confirming the token is valid

#### Scenario: Invalid or expired reset token
- **WHEN** a client posts an invalid, expired, or malformed `uid`/`token` pair
- **THEN** the system returns HTTP 400 and does not change the user’s password

#### Scenario: Activation token rejected for reset validate
- **WHEN** a client posts a valid email-activation token to the password-reset validate endpoint
- **THEN** the system returns HTTP 400

### Requirement: Password-reset confirm endpoint
The system SHALL expose `POST /user_management/password-reset/confirm/` that accepts `{ "uid", "token", "new_password", "confirm_password" }`. The endpoint MUST be public. On success the system MUST set the user’s password using Django’s password hashing, apply the project’s Django password validators, require `new_password` and `confirm_password` to match, invalidate outstanding password-reset tokens for that user (via password hash change), and delete all DRF `Token` rows for that user. Success MUST return HTTP 200 with a success message and MUST NOT issue a new auth token. Invalid/expired tokens or non-customer users MUST fail with HTTP 400 without changing the password.

#### Scenario: Successful confirm
- **WHEN** a client posts a valid customer `uid`/`token` with matching strong `new_password` and `confirm_password`
- **THEN** the system updates the password, deletes all DRF tokens for that user, and returns HTTP 200 without an auth token

#### Scenario: Password mismatch
- **WHEN** `new_password` and `confirm_password` differ
- **THEN** the system returns HTTP 400 with a field validation error and does not change the password

#### Scenario: Weak password rejected
- **WHEN** `new_password` fails Django password validators
- **THEN** the system returns HTTP 400 with validation errors and does not change the password

#### Scenario: Confirm rejects invalid token
- **WHEN** a client posts an invalid or expired `uid`/`token` with otherwise valid passwords
- **THEN** the system returns HTTP 400 and does not change the password

#### Scenario: Prior sessions invalidated
- **WHEN** password reset confirm succeeds for a user who had an existing DRF auth token
- **THEN** that token no longer authenticates subsequent requests

#### Scenario: Reset token cannot be reused after confirm
- **WHEN** a client successfully confirms a password reset and then posts the same `uid`/`token` again
- **THEN** the second confirm returns HTTP 400

### Requirement: Token isolation from email activation
Password-reset tokens MUST be generated and checked with Django’s `PasswordResetTokenGenerator` (or the project’s dedicated reset generator instance), MUST NOT be accepted by email-verification endpoints as proof of email verification, and activation tokens MUST NOT be accepted by password-reset validate/confirm endpoints.

#### Scenario: Activation verify rejects password-reset token
- **WHEN** a client presents a password-reset token to the customer email verification endpoint
- **THEN** verification fails

#### Scenario: Password-reset confirm rejects activation token
- **WHEN** a client presents an email-activation token to password-reset confirm
- **THEN** confirm fails with HTTP 400

### Requirement: Post-reset login uses new password
After a successful password reset, the customer MUST authenticate with the new password via the existing login endpoint. The old password MUST NOT succeed.

#### Scenario: Login with new password
- **WHEN** password reset confirm succeeds and the customer posts login with the new password (and email is verified)
- **THEN** login succeeds and returns a DRF token

#### Scenario: Login with old password fails
- **WHEN** password reset confirm succeeds and the customer posts login with the old password
- **THEN** login fails
