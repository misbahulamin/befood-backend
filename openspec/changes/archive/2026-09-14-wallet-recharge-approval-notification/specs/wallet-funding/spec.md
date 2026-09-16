## ADDED Requirements

### Requirement: Approved pending recharge schedules customer confirmation
When a verified admin successfully approves a pending customer recharge and the wallet credit is committed, the system SHALL schedule customer confirmation side effects (mobile push notification and professional invoice email) after commit without changing the existing credit amount, `completed` status semantics, review fields, or Admin Wallet custody sync rules for that approval. Failure of those side effects MUST NOT reverse the credit or custody movement.

#### Scenario: Successful approve still credits once and notifies after commit
- **WHEN** a verified admin approves a pending recharge of `500.00`
- **THEN** the customer wallet increases by `500.00` exactly once, the transaction is `completed`, Admin Wallet custody sync rules for that recharge still apply, and after commit the system attempts customer push and invoice email side effects

#### Scenario: Notification failure does not undo custody or credit
- **WHEN** post-commit customer notification sending fails after a successful approve
- **THEN** the customer wallet credit and Admin Wallet custody outcome for that approve remain intact
