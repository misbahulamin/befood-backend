## ADDED Requirements

### Requirement: Successful meal-delivery charge credits the Admin Wallet once
When a meal-delivery wallet charge completes successfully for an `OrderDelivery`, the system SHALL also create exactly one completed Admin Wallet credit for the charged amount, linked to that delivery payment with an idempotency key scoped to the delivery (or equivalent unique guard). The customer wallet debit rules defined by this capability remain unchanged: insufficient/frozen wallet still blocks mark-delivered, and retries MUST NOT create a second customer debit or a second Admin Wallet credit.

#### Scenario: Mark delivered credits customer and Admin Wallet together
- **WHEN** an authorized operator marks a `scheduled` delivery as `delivered` and the customer wallet charge of the published slot final price succeeds
- **THEN** the customer wallet has exactly one completed meal-payment debit for that delivery and the Admin Wallet has exactly one completed `customer_payment` credit for the same amount and delivery payment

#### Scenario: Retry after charged delivery does not credit Admin Wallet again
- **WHEN** a delivery is already `delivered` and charged, with Admin Wallet already credited, and mark-delivered is posted again
- **THEN** neither the customer wallet nor the Admin Wallet balance changes due to the retry
