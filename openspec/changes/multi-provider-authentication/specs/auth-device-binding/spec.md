## ADDED Requirements

### Requirement: Upsert device token on successful customer authentication
When a successful customer authentication response is produced (email login, phone OTP verify login/register, Google login, or Facebook login) and the request includes a `device_token` (and optional `platform`), the system SHALL upsert the FCM device token for that user using the existing device-token service rules so push notifications remain associated with the authenticated user, and SHALL reflect the outcome in `device_token_status` on the unified auth response.

#### Scenario: New device token stored on login
- **WHEN** a customer successfully authenticates and supplies a previously unseen `device_token`
- **THEN** the system creates an active `DeviceToken` row for that user and reports a bound/success status in `device_token_status`

#### Scenario: Existing device token reassigned or refreshed
- **WHEN** a customer successfully authenticates with a `device_token` that already exists
- **THEN** the system updates ownership/metadata per existing device-token upsert rules so the token is active for the authenticating user

### Requirement: Multiple devices per user
The system SHALL allow a single customer `User` to have multiple active device tokens so web and mobile clients can receive notifications independently.

#### Scenario: Second device registered both remain active
- **WHEN** the same customer authenticates from device A then device B with different `device_token` values
- **THEN** the system retains both device tokens as active for that user (subject to unique token constraints)

### Requirement: FCM behavior follows logout policy
On current-device logout, when the client supplies the FCM `device_token` for that device, the system SHOULD deactivate that FCM token only. On logout-all or admin force logout, the system MUST deactivate all FCM device tokens for that user (or equivalent documented bulk deactivate).

#### Scenario: Current logout deactivates only supplied FCM token
- **WHEN** a customer logs out on device A and includes device A’s `device_token`
- **THEN** device A’s FCM token is deactivated and other devices’ FCM tokens remain active

#### Scenario: Logout-all deactivates all FCM tokens
- **WHEN** a customer calls logout-all
- **THEN** all FCM device tokens for that user are deactivated
