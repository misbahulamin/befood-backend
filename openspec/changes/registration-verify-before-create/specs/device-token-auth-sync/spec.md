## ADDED Requirements

### Requirement: Device tokens upsert for authenticated customers
The system SHALL create or update FCM device tokens for an authenticated customer using the existing device-token registration service. When the submitted token value already exists, the system MUST update that row (user association, platform metadata, `is_active`, `last_used_at`) and MUST NOT insert a duplicate row for the same token value. When the token does not exist, the system MUST create a new `DeviceToken` associated with the authenticated user.

#### Scenario: First token for a user is created
- **WHEN** an authenticated customer registers a device token that is not yet stored
- **THEN** the system creates a new active `DeviceToken` linked to that user

#### Scenario: Existing token value is updated not duplicated
- **WHEN** an authenticated customer registers a token value that already exists in storage
- **THEN** the system updates the existing row (including reassigning the user if the device changed accounts) and does not create a second row with the same token

### Requirement: Mobile auth success triggers device-token sync
The system SHALL ensure that customers who authenticate on the mobile app end up with a valid device-token association for push delivery. Successful mobile login MUST result in a device-token upsert for the current FCM token (via the dedicated device-token API and/or an optional login payload that invokes the same upsert service). Registration alone MUST NOT be required to persist a device token before email verification completes.

#### Scenario: Mobile login after web registration syncs token
- **WHEN** a customer creates an account via the website verification flow and later logs in on the mobile app with a valid FCM token available
- **THEN** the backend stores or updates that token for the customer so push notifications can be delivered

#### Scenario: Returning mobile login refreshes token
- **WHEN** an existing customer logs in on the mobile app and the app submits the current FCM token
- **THEN** the system upserts the token for that user without creating duplicates for the same token value

#### Scenario: Unauthenticated register does not require device token
- **WHEN** a client completes registration before verification
- **THEN** the system does not require a device token on the register request and does not leave an orphan token without a verified user

### Requirement: Multi-device tokens remain allowed
The system SHALL continue to allow multiple distinct token values for the same user (multiple devices). Upsert uniqueness remains on the token string, not a hard single-row-per-user constraint.

#### Scenario: Second device adds another token
- **WHEN** the same authenticated user registers a different FCM token from another device
- **THEN** the system creates an additional active token row for that user
