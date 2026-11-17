# Spec Delta

## ADDED Requirements

### Requirement: FCM batches are platform-aware for native and web tokens

When sending to a mixed set of device tokens, the system MUST construct FCM messages so Android/iOS native delivery continues to use Android notification channel configuration, and web tokens receive web push options separately. A web-only configuration failure MUST NOT prevent successful delivery to valid native tokens in the same campaign.

#### Scenario: Mixed android and web tokens both attempted

- **WHEN** a campaign has pending recipients with both `android` and `web` active tokens
- **THEN** the system attempts FCM delivery for both platforms and records per-token success or failure independently

#### Scenario: Native tokens succeed when web tokens fail

- **WHEN** FCM rejects web tokens but accepts android tokens in the same campaign
- **THEN** android recipient rows become `sent`, web recipient rows become `failed`, and the campaign reaches a terminal status with `total_sent` equal to the android successes

### Requirement: Unexpected FCM send errors are captured per campaign safely

If the FCM send helper raises an unexpected exception after dispatch starts, the system MUST mark remaining pending recipients as `failed` with a safe error message, set campaign `status` to `failed` or `completed` according to whether any sends already succeeded, and MUST NOT leave the campaign in `processing`.

#### Scenario: Unexpected FCM exception finalizes campaign

- **WHEN** FCM send raises an unexpected exception after inbox creation
- **THEN** the campaign is no longer `processing`, pending recipients are marked `failed`, and `error_summary` or recipient `error_message` contains a safe client-facing reason without stack traces

## MODIFIED Requirements

### Requirement: Invalid FCM tokens are deactivated automatically

When Firebase returns an invalid or unregistered registration token error, the system MUST soft-deactivate the corresponding `DeviceToken` row and mark the recipient `status=failed`. Transient or platform-mismatch errors that are not clearly unregistered/invalid MUST NOT deactivate tokens.

#### Scenario: Unregistered token deactivated

- **WHEN** FCM returns an unregistered/invalid token error for a device
- **THEN** the system sets `DeviceToken.is_active=False` and marks the recipient `status=failed`

#### Scenario: Non-invalid send error keeps token active

- **WHEN** FCM returns a non-invalid transient send error for a device
- **THEN** the recipient is marked `failed` and the `DeviceToken` remains `is_active=True`
