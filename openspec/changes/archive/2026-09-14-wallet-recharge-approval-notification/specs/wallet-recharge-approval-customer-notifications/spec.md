## ADDED Requirements

### Requirement: Customer push on approved recharge
After a pending customer wallet recharge is successfully approved and committed as `completed`, the system SHALL schedule a Firebase Cloud Messaging (FCM) push notification to that customer's registered device tokens using `transaction.on_commit` (or equivalent). The push MUST include a clear recharge-success message, the approved recharge amount, the updated wallet balance, and enough timing context for the customer (body text and/or data payload with an approval/completion timestamp). The on-commit callback MUST catch and log FCM/send exceptions so a push failure cannot turn the already-committed approval into an HTTP failure. If the customer has no registered device tokens, the system MUST skip push and MUST NOT fail approval.

#### Scenario: Approved recharge triggers customer push after commit
- **WHEN** a verified admin successfully approves a pending recharge of `1000.00` and the customer has at least one device token
- **THEN** after commit the system attempts to send a push whose body communicates successful approval of `1000.00` and the updated wallet balance

#### Scenario: Push failure keeps approved recharge
- **WHEN** FCM fails inside the post-commit callback after recharge approval was committed
- **THEN** the recharge remains `completed`, the wallet credit remains applied, the HTTP approve remains successful, and the failure is logged

#### Scenario: No device tokens skips push without failing approval
- **WHEN** a verified admin approves a pending recharge for a customer with no device tokens
- **THEN** the approval succeeds and no push send is required

### Requirement: Approve conflict does not resend customer notifications
Customer push (and the companion invoice email orchestration for the same approval event) MUST be scheduled only when `approve_recharge` actually transitions a recharge from `pending` to `completed`. A subsequent approve attempt on an already-processed request MUST return the existing conflict outcome without scheduling another customer notification.

#### Scenario: Second approve does not resend push
- **WHEN** a pending recharge was already approved and customer notifications were scheduled, and a verified admin attempts to approve the same request again
- **THEN** the system responds with conflict (`409` or equivalent existing funding conflict behavior) and does not schedule another customer push

### Requirement: FCM data payload is mobile-routable
The recharge-approval push data payload MUST use string values and MUST include at least `type=wallet_recharge_approved`, `entity_type=wallet_transaction`, and `entity_id` set to the wallet transaction `public_id`. It SHOULD include a documented `screen` key for wallet navigation consistent with the project's FCM routing conventions.

#### Scenario: Payload identifies the wallet transaction
- **WHEN** a recharge-approval push is sent
- **THEN** the data payload includes `type=wallet_recharge_approved` and `entity_id` equal to the completed transaction `public_id`
