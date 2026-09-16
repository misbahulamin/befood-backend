## ADDED Requirements

### Requirement: Deferred email registration does not create a production user
The system SHALL accept customer email registration into a pending registration record without creating a Django `User` or `CustomerProfile` until email verification succeeds. The pending record MUST store a hashed password and MUST expire per configured pending-registration TTL. Incoming emails MUST be processed with `normalize_email()` (`lower().strip()`) before storage and uniqueness checks.

#### Scenario: Successful pending registration
- **WHEN** an unauthenticated client submits a valid unused email and password to the customer register endpoint
- **THEN** the system responds successfully without creating a production `User`, stores a pending registration under the normalized email, and sends an email verification message containing an OTP and/or verification link

#### Scenario: Duplicate of active customer email rejected
- **WHEN** a client registers with an email that already belongs to an active customer `User` after normalization
- **THEN** the system rejects the registration with a validation error and does not create a new pending or production account

#### Scenario: Email case variants are treated as the same identity
- **WHEN** a client registers with `Test@gmail.com` and a customer or pending record already exists for `test@gmail.com`
- **THEN** the system treats them as the same email and rejects or upserts per existing duplicate rules without creating a second distinct identity

### Requirement: Email verification activates the customer account
The system SHALL finalize a pending customer registration only after a valid email verification OTP or link is presented. Finalization MUST create an active `User`, a `CustomerProfile` with `is_email_verified=True`, assign the `CUSTOMER` group, and invalidate the pending record.

#### Scenario: OTP verification finalizes account
- **WHEN** a client submits a valid unexpired email verification OTP for a pending registration
- **THEN** the system creates the production customer user and profile as verified and the pending registration is no longer usable for that email

#### Scenario: Invalid or expired verification rejected
- **WHEN** a client submits an invalid or expired email verification OTP or link
- **THEN** the system rejects the request and does not create a production user

### Requirement: Email login requires verified credentials
The system SHALL authenticate customer email+password login using normalized email and issue an auth session token only for an existing active customer with verified email (or documented legacy handling that refuses unverified accounts without promoting them to production status via login alone). On success the system MUST return the unified auth success response.

#### Scenario: Successful email login
- **WHEN** a verified customer submits correct email (any case) and password to the customer login endpoint
- **THEN** the system responds `200` with the unified auth envelope including `token`, `user`, `customer_profile`, and `device_token_status`

#### Scenario: Unverified or pending-only email cannot obtain a production session via login alone
- **WHEN** a client attempts login for an email that is only pending registration or is an unverified legacy account that is not eligible
- **THEN** the system does not issue a successful production session token as if the account were fully verified, and returns the existing documented error behavior for that case
