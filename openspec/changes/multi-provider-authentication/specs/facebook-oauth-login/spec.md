## ADDED Requirements

### Requirement: Verify Facebook token on the backend
The system SHALL provide a customer Facebook login endpoint that accepts a Facebook access token, verifies it with Facebook Graph API using configured `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, and `FACEBOOK_GRAPH_VERSION`, and MUST reject tokens that are invalid for this app. The system MUST NOT trust client-supplied Facebook profile fields without successful token verification.

#### Scenario: Valid Facebook token accepted
- **WHEN** a client submits a Facebook access token that Graph API validates for this app
- **THEN** the system extracts the stable Facebook user id and available profile claims needed for account resolution

#### Scenario: Invalid Facebook token rejected
- **WHEN** a client submits an invalid or app-mismatched Facebook token
- **THEN** the system responds with an authentication/validation error and does not create or log in a user

### Requirement: Facebook login creates or authenticates a customer
After successful Facebook verification, the system SHALL resolve the customer via social linking rules and issue an auth session token for the resulting customer `User` in the `CUSTOMER` group. New accounts MUST create a `CustomerProfile`, persist a Facebook `SocialIdentity` with provider `facebook`, call `set_unusable_password()` on the new `User`, and return the unified auth success response.

#### Scenario: New Facebook user is password-less
- **WHEN** a verified Facebook credential does not match an existing social identity or linkable verified customer
- **THEN** the system creates a new customer account with an unusable password, stores the Facebook provider user id, and returns the unified auth envelope

#### Scenario: Returning Facebook user
- **WHEN** a verified Facebook credential matches an existing Facebook social identity
- **THEN** the system logs in that user and returns the unified auth envelope without creating a duplicate account
