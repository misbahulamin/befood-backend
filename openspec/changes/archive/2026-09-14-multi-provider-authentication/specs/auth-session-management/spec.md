## ADDED Requirements

### Requirement: Long-lived customer sessions
The system SHALL authenticate customers via opaque auth session keys presented with Token-compatible headers for email, phone OTP, Google, and Facebook success paths. Issued sessions MUST remain valid until the user explicitly logs out (current or all), or the system invalidates sessions for a documented security revoke event. The system MUST NOT apply idle-timeout or sliding automatic logout for normal customer sessions.

#### Scenario: Session remains valid without idle logout
- **WHEN** a customer obtained a token earlier and later calls an authenticated endpoint with that token without having logged out
- **THEN** the system authenticates the request successfully regardless of elapsed idle time (barring explicit invalidation events)

### Requirement: Unified auth success response
All successful customer authentication methods (email login, phone OTP verify, Google, Facebook) MUST return the same response envelope shape including at least `token`, `user`, `customer_profile`, and `device_token_status` (plus documented shared additive fields such as `auth_provider` / `groups`).

#### Scenario: Email and phone login share envelope fields
- **WHEN** a client completes email login and separately completes phone OTP verify successfully
- **THEN** both responses include the same top-level keys required by the unified envelope

### Requirement: Current-device logout
The system SHALL provide a default customer logout endpoint that revokes only the **current** auth session so other devices remain signed in. Subsequent requests with the revoked token MUST fail with `401`.

#### Scenario: Logout current leaves other sessions active
- **WHEN** a customer is authenticated on device A and device B with distinct sessions and calls logout on device A
- **THEN** device A’s token is unauthorized and device B’s token continues to authenticate

### Requirement: Logout-all devices
The system SHALL provide a separate authenticated logout-all endpoint that revokes every auth session for the customer so all devices must sign in again.

#### Scenario: Logout-all revokes every session
- **WHEN** an authenticated customer calls logout-all while multiple sessions exist
- **THEN** all of that user’s session tokens become unauthorized

### Requirement: Security revoke events
The system SHALL document and support session revocation for at least: manual current logout, manual logout-all, password reset (when applicable), and admin force logout. A suspicious-login revoke hook MUST be reserved for future detection without requiring full detection product in this change.

#### Scenario: Admin force logout clears all sessions
- **WHEN** an authorized admin force-logout action runs for a customer
- **THEN** all auth sessions for that customer are revoked

### Requirement: Current authenticated customer profile
The system SHALL expose a current-user (`me`) endpoint that returns the authenticated customer’s identity summary when a valid session token is presented and rejects unauthenticated callers with `401`.

#### Scenario: Me with valid token
- **WHEN** a customer calls `me` with a valid auth token
- **THEN** the system returns `200` with the customer user summary

#### Scenario: Me without token
- **WHEN** a client calls `me` without valid authentication
- **THEN** the system responds `401`
