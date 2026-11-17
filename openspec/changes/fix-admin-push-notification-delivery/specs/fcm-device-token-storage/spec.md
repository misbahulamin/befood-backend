# Spec Delta

## ADDED Requirements

### Requirement: DeviceToken token column supports web push length

The `DeviceToken.token` column MUST allow values up to 512 characters so Flutter web / PWA FCM registration tokens can be stored without truncation. Uniqueness of `token` MUST remain enforced.

#### Scenario: 512-character token persists

- **WHEN** a device registration stores a token of length 512
- **THEN** the full token value is persisted and later FCM send uses the untruncated value

#### Scenario: Token longer than 512 rejected before persistence

- **WHEN** a registration attempt supplies a token longer than 512 characters
- **THEN** the system rejects the request at validation and does not persist a truncated token
