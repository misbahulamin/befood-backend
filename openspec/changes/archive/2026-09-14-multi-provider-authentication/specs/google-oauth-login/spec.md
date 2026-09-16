## ADDED Requirements

### Requirement: Verify Google credential on the backend
The system SHALL provide a customer Google login endpoint that accepts a Google credential from the client, verifies it on the server using configured Google client IDs (`GOOGLE_WEB_CLIENT_ID` and/or `GOOGLE_ANDROID_CLIENT_ID`), and MUST reject tokens that fail signature, audience, issuer, or expiry checks. The system MUST NOT trust client-supplied Google profile fields without successful token verification.

#### Scenario: Valid Google credential accepted
- **WHEN** a client submits a valid Google ID token whose audience matches a configured client ID
- **THEN** the system extracts the stable Google subject identifier and verified profile claims needed for account resolution

#### Scenario: Invalid Google credential rejected
- **WHEN** a client submits an invalid, expired, or wrong-audience Google credential
- **THEN** the system responds with an authentication/validation error and does not create or log in a user

### Requirement: Google login creates or authenticates a customer
After successful Google verification, the system SHALL resolve the customer via social linking rules and issue an auth session token for the resulting customer `User` in the `CUSTOMER` group. New accounts MUST create a `CustomerProfile`, persist a Google `SocialIdentity` with provider `google`, call `set_unusable_password()` on the new `User`, and return the unified auth success response.

#### Scenario: New Google user is password-less
- **WHEN** a verified Google credential does not match an existing social identity or linkable verified customer
- **THEN** the system creates a new customer account with an unusable password, stores the Google provider user id, and returns the unified auth envelope

#### Scenario: Returning Google user
- **WHEN** a verified Google credential matches an existing Google social identity
- **THEN** the system logs in that user and returns the unified auth envelope without creating a duplicate account
