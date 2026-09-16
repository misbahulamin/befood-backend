## ADDED Requirements

### Requirement: Notify customer when meal is marked delivered

When an `OrderDelivery` successfully transitions to `delivered` (via admin mark or auto-delivery), the system SHALL attempt to notify the delivery's customer that the meal was delivered. Notification failure MUST NOT roll back delivery status or wallet debit.

#### Scenario: Auto-delivery sends notification after charge

- **WHEN** auto-delivery successfully marks a scheduled slot as `delivered` and charges the wallet
- **THEN** the system attempts to send a delivery notification to that customer

#### Scenario: Admin mark delivered also notifies

- **WHEN** an authorized admin marks a scheduled slot as `delivered` successfully
- **THEN** the system attempts to send the same class of delivery notification to that customer

#### Scenario: Notification failure keeps delivery delivered

- **WHEN** delivery mark and wallet charge succeed but FCM/device delivery fails
- **THEN** the slot remains `delivered` and charged, and the failure is logged

### Requirement: Skipped meals do not send delivered notification

The system MUST NOT send a “meal delivered” notification when a slot is marked `skipped` (customer meal-off or admin skip).

#### Scenario: Admin skip has no delivered push

- **WHEN** an admin marks a slot as `skipped`
- **THEN** the system does not send a meal-delivered notification for that slot
