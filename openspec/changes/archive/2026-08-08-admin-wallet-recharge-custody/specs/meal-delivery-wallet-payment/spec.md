## ADDED Requirements

### Requirement: Meal-delivery charge does not double-credit Admin Wallet cash
After a successful customer meal-delivery wallet charge, the system MUST NOT create an Admin Wallet cash credit that increases platform balance for that same charge. Customer wallet debit, delivery payment status, and meal-payment history rules from this capability remain unchanged.

#### Scenario: Successful meal charge does not increase Admin Wallet cash
- **WHEN** an authorized operator marks a delivery `delivered` and the customer wallet is successfully debited for the slot price
- **THEN** the customer meal-payment debit exists as today, and the Admin Wallet cash balance does not increase solely because of that meal charge

#### Scenario: Retry mark-delivered still does not cash-credit Admin Wallet
- **WHEN** a delivery was already charged and mark-delivered is posted again
- **THEN** neither the customer wallet nor the Admin Wallet cash balance changes due to the retry, and no additional Admin Wallet cash credit is created for that delivery payment
