## ADDED Requirements

### Requirement: Admin email on pending recharge submit
After a **new** customer recharge request is successfully committed as `pending`, the system SHALL schedule an email notification to relevant verified admin recipients using `transaction.on_commit` (or equivalent post-commit hook). The on-commit callback MUST catch and log email/SMTP exceptions so a send failure cannot turn the already-committed create into an HTTP failure. The email MUST include at least customer name, customer email or identifier, amount, payment method, transaction id, request `public_id`, and submission time. The message MUST instruct admins to verify the off-platform payment and approve or reject in the admin panel. An idempotent replay that returns an existing funding request (regardless of whether its current status is still `pending` or later became `completed`/`failed`) MUST NOT schedule or send another admin email.

#### Scenario: Pending recharge triggers admin email attempt after commit
- **WHEN** a verified customer successfully creates a new pending recharge
- **THEN** after commit the system attempts to email verified admin recipients with the recharge review details

#### Scenario: Email failure keeps pending recharge
- **WHEN** SMTP fails inside the post-commit callback after a pending recharge was committed
- **THEN** the pending recharge remains stored, the HTTP create remains successful, and the failure is logged

#### Scenario: Idempotent recharge replay does not resend email
- **WHEN** a customer replays the same recharge idempotency key and payload after the original create already notified admins (including after the row was later approved or rejected)
- **THEN** the system returns the existing transaction with its current persisted status and does not send another admin email

### Requirement: Admin email on pending withdraw submit
After a **new** customer withdraw request is successfully committed as `pending`, the system SHALL schedule an email notification to relevant verified admin recipients using `transaction.on_commit` (or equivalent). The on-commit callback MUST catch and log email/SMTP exceptions. The email MUST include at least customer name, customer email or identifier, withdrawal amount, request `public_id`, and submission time, and MAY include current spendable balance after reservation. The message MUST instruct admins to send the payout manually and then approve in the admin panel. An idempotent replay that returns an existing withdraw request (any current persisted status) MUST NOT schedule or send another admin email.

#### Scenario: Pending withdraw triggers admin email attempt after commit
- **WHEN** a verified customer successfully creates a new pending withdraw
- **THEN** after commit the system attempts to email verified admin recipients with the withdraw review details

#### Scenario: Email failure keeps pending withdraw and reservation
- **WHEN** SMTP fails inside the post-commit callback after a pending withdraw was committed
- **THEN** the pending withdraw remains stored with its balance reservation intact, the HTTP create remains successful, and the failure is logged

#### Scenario: Idempotent withdraw replay does not resend email
- **WHEN** a customer replays the same withdraw idempotency key and payload after the original create already notified admins (including after later approve/reject)
- **THEN** the system returns the existing transaction with its current persisted status and does not send another admin email

### Requirement: Admin funding email recipients are verified admins
The system SHALL determine funding-notification recipients from active users who are verified admins according to existing admin verification rules (verified `AdminProfile` with admin group access) and active superusers with a usable email. The system MUST reuse the project’s existing email sending stack and MUST NOT introduce a new mail provider library for this capability.

#### Scenario: Unverified admin is not a required recipient
- **WHEN** an admin profile exists with `is_verified=false`
- **THEN** that address is not required to be included in funding notification recipients
