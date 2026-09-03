## ADDED Requirements

### Requirement: Unique invoice identity for transaction receipts
The system SHALL assign a unique human-readable invoice number to each wallet recharge receipt generated for an approved customer recharge. The invoice number MUST be persisted with the related wallet transaction (dedicated field or equivalent durable storage) so the same approval cannot receive two different invoice numbers. Invoice numbering MUST be designed so future non-recharge transaction receipts can reuse the same identity service or naming scheme without rewriting the recharge approve path.

#### Scenario: Approved recharge gets one invoice number
- **WHEN** a pending recharge is approved and an invoice is generated
- **THEN** exactly one unique invoice number is stored for that wallet transaction

#### Scenario: Invoice number is stable across notification retries
- **WHEN** invoice email sending is retried for the same approved wallet transaction after a transient SMTP failure
- **THEN** the system continues to use the same persisted invoice number

### Requirement: Reusable branded invoice template structure
The system SHALL provide a reusable invoice email template structure (base blocks and/or shared context builder) that supplies brand header assets (logo, company name), configurable contact information, and social links when available, plus a structured invoice body section. Wallet recharge MUST be the first concrete invoice type using this structure. The context builder MUST expose a stable set of keys (invoice number, customer fields, amounts, status, dates, optional references) so additional invoice types can extend line-item content without forking branding.

#### Scenario: Recharge invoice uses shared branding context
- **WHEN** a wallet recharge invoice email is rendered
- **THEN** it uses the shared brand context (logo URL and brand colors when configured) rather than a one-off unbranded layout

#### Scenario: Context supports extension beyond recharge
- **WHEN** a developer inspects the invoice context builder / template structure
- **THEN** invoice identity and customer/amount sections are separated from recharge-specific labels so another transaction type can reuse the structure

### Requirement: Previous balance snapshot for recharge invoices
When generating a recharge invoice at approve time, the system MUST determine previous wallet balance as the balance immediately before the approval credit (equivalently `balance_after - amount` for that completed credit) and MUST present that value on the invoice together with the updated balance.

#### Scenario: Previous balance matches pre-credit wallet
- **WHEN** a wallet with balance `500.00` receives an approved recharge of `1000.00`
- **THEN** the invoice shows previous balance `500.00` and updated balance `1500.00`
