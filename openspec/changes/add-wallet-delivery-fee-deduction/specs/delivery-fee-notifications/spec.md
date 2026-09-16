## ADDED Requirements

### Requirement: Customer is notified after successful delivery-fee deduction

After a verified admin successfully deducts a delivery fee, the system MUST notify the customer with an inbox notification and attempt FCM push delivery using the existing notification infrastructure. Notification MUST run after the money transaction commits (best-effort) and MUST NOT roll back or fail the wallet debit if push/inbox delivery fails.

#### Scenario: Inbox notification created on deduct

- **WHEN** September 2026 delivery fee `300.00` is deducted and the customer’s new balance is `950.00`
- **THEN** an inbox notification exists for that customer with title indicating delivery fee deducted and body referencing September, amount `300`, and current balance `950`

#### Scenario: Push send is attempted

- **WHEN** the customer has registered device tokens
- **THEN** the system attempts FCM delivery for the delivery-fee deduction notification after commit

#### Scenario: Notification failure does not undo debit

- **WHEN** FCM send fails after a successful deduct
- **THEN** the wallet debit and paid delivery-fee payment remain committed

### Requirement: Delivery-fee notification is stored in notification history

The created inbox notification MUST be queryable in the customer’s notification history with a stable notification type (for example `delivery_fee_deducted`) and SHOULD include structured data suitable for deep-linking to the wallet screen.

#### Scenario: History lists delivery-fee notification

- **WHEN** the customer lists notifications after a successful deduct
- **THEN** the delivery-fee deduction notification appears in history with its type and body
