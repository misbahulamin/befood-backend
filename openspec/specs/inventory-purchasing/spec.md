## Purpose

Inventory purchasing workflow: multi-line purchases, optional invoice upload, additive stock receipt, atomic Admin Wallet debit on confirm, bidirectional wallet links, filtered purchase history, and compensating cancel.

## Requirements

### Requirement: Verified admin can create inventory purchases
The system SHALL allow verified admins to create inventory purchase records that include one or more lines, each with inventory item, quantity, unit, line total amount, and derived or provided unit cost. A purchase MUST capture purchase date/time (system timestamps plus optional business purchase date), optional supplier/vendor, optional note, optional invoice/receipt file, acting admin, status, and computed total amount. Clients MUST address purchases by `public_id`.

#### Scenario: Create single-line purchase draft or pending confirm
- **WHEN** a verified admin creates a purchase for Beef `50` kg with total `25000.00` BDT
- **THEN** the system stores the purchase with line unit cost `500.00`, acting admin, and a non-confirmed or explicitly draft status until confirmation rules are satisfied

#### Scenario: Multi-line purchase totals
- **WHEN** a verified admin creates a purchase with two lines totaling `10000.00` and `5000.00`
- **THEN** the purchase total amount equals `15000.00`

### Requirement: Invoice or receipt upload on purchase
The system SHALL allow uploading an invoice/receipt file linked to a purchase. Accepted content types MUST include JPEG, PNG, and PDF. Unsupported types or oversized files MUST be rejected. Verified admins MUST be able to open or download the linked invoice from purchase detail/history. Confirming a purchase MUST be allowed when no invoice is present (invoice optional), and audit metadata SHOULD note when confirm proceeds without an invoice.

#### Scenario: Upload PNG invoice
- **WHEN** a verified admin attaches a PNG receipt to a purchase
- **THEN** the file is stored and available from the purchase record

#### Scenario: Reject unsupported invoice type
- **WHEN** a verified admin uploads an executable or unsupported file type as an invoice
- **THEN** the system rejects the upload and does not link the file

### Requirement: Confirm purchase adds stock and debits Admin Wallet atomically
The system SHALL confirm a purchase in a single database transaction that (1) validates Admin Wallet available balance is greater than or equal to the purchase total, (2) posts additive stock movements for each line without overwriting prior on-hand, (3) updates weighted average costs, and (4) debits the Admin Wallet with type `inventory_purchase` for the purchase total, recording acting admin, source/reference to the purchase, and an idempotency key scoped to the purchase. If any step fails, the system MUST roll back stock and wallet changes. Successful confirm MUST set purchase status to confirmed and store a reference to the wallet transaction.

#### Scenario: Confirm with sufficient wallet balance
- **WHEN** Admin Wallet balance is `200000.00` and a purchase totaling `35000.00` is confirmed
- **THEN** wallet balance becomes `165000.00`, stock increases by purchased quantities, and a completed `inventory_purchase` debit of `35000.00` exists linked to the purchase

#### Scenario: Insufficient wallet balance rejects confirm
- **WHEN** Admin Wallet balance is `10000.00` and a purchase totaling `15000.00` is confirmed
- **THEN** the system rejects confirm with a client-safe insufficient wallet balance error, does not add stock, and does not create a completed wallet debit

#### Scenario: Idempotent confirm replay
- **WHEN** the same confirmed purchase confirm/debit path is retried with the same idempotency key
- **THEN** the system does not double-debit the wallet and does not double-post stock

### Requirement: Purchase does not overwrite existing stock
When a purchase is confirmed for an item that already has on-hand quantity, the system MUST add the purchased quantity to the existing on-hand quantity rather than replacing it.

#### Scenario: Additive stock on repurchase
- **WHEN** Beef on-hand is `5` kg and a purchase of `50` kg Beef is confirmed
- **THEN** Beef on-hand becomes `55` kg

### Requirement: Bidirectional wallet and purchase reconciliation links
A confirmed purchase MUST expose a reference to its Admin Wallet transaction, and the related Admin Wallet transaction MUST be filterable or detail-linked back to the inventory purchase (via reference/metadata and/or foreign key). Admins MUST be able to navigate conceptually from purchase history to wallet transaction and from wallet transaction to inventory purchase.

#### Scenario: Purchase shows wallet transaction reference
- **WHEN** a purchase is confirmed and wallet debit succeeds
- **THEN** purchase detail includes the wallet transaction `public_id` (or equivalent stable reference)

### Requirement: Purchase history with allowlisted filters
The system SHALL provide a paginated purchase history for verified admins including purchase identity, date, item/lines, quantities, units, amounts, unit costs, invoice availability, added-by admin, wallet transaction reference, and status. Filters MUST be allowlisted and MUST include at least date range, item, admin, category, amount bounds, and supplier. Unsupported filter parameters MUST be rejected with `400`.

#### Scenario: Filter purchases by date range and item
- **WHEN** a verified admin requests purchase history for a date range and item Beef
- **THEN** only matching purchases are returned in deterministic order

### Requirement: Cancel confirmed purchase with stock and wallet compensation
The system SHALL allow cancelling a confirmed purchase only when doing so would not drive any item negative under the v1 cancel rule (sufficient remaining on-hand to reverse each line’s purchased quantity). Cancel MUST atomically post reversing stock movements and credit/compensate the Admin Wallet for the original debit amount with audit logging. Draft/unconfirmed purchases MUST be discardable without wallet impact.

#### Scenario: Cancel when full purchased qty still on hand
- **WHEN** a confirmed Beef purchase of `50` kg exists, on-hand is at least `50` kg attributable under the cancel rule, and an admin cancels the purchase
- **THEN** stock decreases by `50` kg, wallet is compensated by the original purchase amount, and purchase status becomes cancelled

#### Scenario: Cancel blocked when stock already consumed
- **WHEN** purchased quantity has already been consumed such that cancel would violate the cancel rule
- **THEN** the system rejects cancel and leaves stock and wallet unchanged
