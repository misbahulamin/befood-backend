## ADDED Requirements

### Requirement: Offline customer receives FCM when admin replies

When a verified admin successfully posts a support reply (REST or WebSocket) and the customer has **no active support WebSocket presence** for that conversation, the system SHALL schedule a best-effort customer alert using existing `create_inbox_notification` and FCM send helpers. Payload MUST include support routing keys (`type`/`screen`) and conversation public id strings. FCM/inbox failure MUST NOT roll back the support message.

#### Scenario: Offline customer gets push on admin reply

- **WHEN** an admin reply is saved and the customer is not present on the conversation WebSocket
- **THEN** the system attempts in-app inbox notification and FCM to the customer's device tokens

#### Scenario: Online customer skips redundant push

- **WHEN** an admin reply is saved and the customer is actively present on the conversation WebSocket
- **THEN** the system MUST still persist the message and MAY skip FCM to avoid duplicate alerts while the live event is delivered

#### Scenario: Message persists if push fails

- **WHEN** FCM is misconfigured or send fails after an admin reply is saved
- **THEN** the support message remains stored and the reply still succeeds

### Requirement: Offline admins are notified when customer messages

When a customer successfully posts a support message and no verified admin has active support presence (conversation and/or admin inbox presence per design), the system SHALL schedule a best-effort admin notification using the existing verified-admin email recipient pattern (and MUST NOT invent a second push platform). Email failure MUST NOT roll back the message.

#### Scenario: Customer message emails admins when none online

- **WHEN** a customer message is saved and no admin support presence is detected
- **THEN** the system attempts to email verified admins with customer context and a message preview

#### Scenario: Message persists if email fails

- **WHEN** SMTP delivery fails after a customer message is saved
- **THEN** the support message remains stored and the customer send still succeeds

### Requirement: No parallel notification stack

Support messaging MUST reuse existing notification/FCM/email utilities. Canonical message bodies MUST live on `SupportMessage`; any `Notification` row is an alert copy only.

#### Scenario: Conversation body not stored only as Notification

- **WHEN** a support message is created
- **THEN** the canonical body MUST be stored on the support message model
