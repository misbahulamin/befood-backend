## ADDED Requirements

### Requirement: Branded invoice email on approved recharge
After a pending customer wallet recharge is successfully approved and committed as `completed`, the system SHALL schedule a professional invoice email to the customer's account email using `transaction.on_commit` (or equivalent), after wallet credit has been persisted. The email MUST use the project's existing branded email infrastructure (logo, brand colors, company contact and social links when configured) and MUST provide both HTML and plain-text alternatives. SMTP/send failures MUST be caught and logged so they cannot roll back the approved recharge or HTTP success. If the customer has no usable email address, the system MUST skip the invoice email and MUST NOT fail approval.

#### Scenario: Approved recharge sends invoice email after commit
- **WHEN** a verified admin successfully approves a pending recharge for a customer with a usable email
- **THEN** after commit the system attempts to email that address a branded recharge invoice

#### Scenario: Invoice email failure keeps approved recharge
- **WHEN** SMTP fails inside the post-commit invoice send after approval was committed
- **THEN** the recharge remains `completed`, the wallet credit remains applied, the HTTP approve remains successful, and the failure is logged

#### Scenario: Missing customer email skips invoice without failing approval
- **WHEN** a verified admin approves a pending recharge for a customer without a usable email
- **THEN** the approval succeeds and no invoice email send is required

### Requirement: Invoice email content for wallet recharge
The recharge invoice email MUST include: a unique invoice number; customer name; customer email; customer phone when available; recharge date/time; payment method; provider/transaction id when present (`external_ref`); recharge amount; previous wallet balance; updated wallet balance; and status indicating approved/completed. The layout MUST be a clean, readable business-invoice style suitable for mobile and desktop email clients and MUST maintain Befood brand identity.

#### Scenario: Invoice lists recharge and balance fields
- **WHEN** a recharge invoice email is generated for an approved txn of `1000.00` that raised balance from `500.00` to `1500.00`
- **THEN** the email content includes invoice number, customer identity fields, payment method, amount `1000.00`, previous balance `500.00`, updated balance `1500.00`, and completed/approved status

#### Scenario: Provider transaction id included when present
- **WHEN** the approved recharge has a non-empty `external_ref`
- **THEN** the invoice email includes that value as the transaction/payment reference

### Requirement: Invoice email is not resent on approve conflict
The invoice email MUST be scheduled only on the successful `pending → completed` approve transition. Re-approve conflict responses MUST NOT schedule another invoice email for the same wallet transaction.

#### Scenario: Second approve does not resend invoice
- **WHEN** a recharge was already approved and invoiced, and admin attempts approve again
- **THEN** the system returns conflict without sending another invoice email
