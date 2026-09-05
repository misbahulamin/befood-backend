## ADDED Requirements

### Requirement: Email-first status check

The system SHALL provide an unauthenticated customer email-check endpoint that accepts an email, normalizes it, and returns a branch status without creating a User, issuing a token, or returning password material.

#### Scenario: Existing verified email customer

- **WHEN** a client submits an email that matches a customer with `is_email_verified=True`
- **THEN** the system responds with status indicating the email already exists and the client MUST proceed to password login

#### Scenario: Pending deferred registration

- **WHEN** a client submits an email that has an active `PendingCustomerRegistration` and no verified production customer for that email
- **THEN** the system responds with status indicating pending registration so the client can continue verification / registration UX

#### Scenario: Email available for registration

- **WHEN** a client submits an email that is neither a verified customer nor a pending registration
- **THEN** the system responds with status indicating the email is available for new deferred registration

#### Scenario: Invalid email rejected

- **WHEN** a client submits a malformed email
- **THEN** the system returns a validation error and does not return an existence status

### Requirement: Email check uses normalized identity

The system MUST apply the same email normalization used by register and login (`lower().strip()` / `normalize_email`) before comparing against User and pending registration records.

#### Scenario: Case-insensitive match

- **WHEN** a client checks `Test@Example.com` and a verified customer exists as `test@example.com`
- **THEN** the system returns the existing-customer status
