## ADDED Requirements

### Requirement: Delivery fee payments are persisted as first-class ledger rows

The system SHALL persist each successful delivery-fee collection as a `DeliveryFeePayment` record with at least: opaque `public_id`, customer reference, decimal `amount` (BDT, two fractional digits), `payment_month` (1–12), `payment_year`, `status`, `deducted_by_admin` reference, linked customer `wallet_transaction`, `reason`, `source` (`manual` or `automatic`), timestamps, and optional future-automation fields (`fee_rule_code`, service-area reference or equivalent nullable metadata). Completed monetary fields on a paid row MUST NOT be mutated in place.

#### Scenario: Successful deduct creates payment row

- **WHEN** a verified admin successfully deducts a delivery fee for a customer for September 2026
- **THEN** a `DeliveryFeePayment` exists with that customer, amount, `payment_month=9`, `payment_year=2026`, `status=paid`, actor admin set, and a linked completed wallet debit

#### Scenario: Paid monetary fields are immutable

- **WHEN** a delivery-fee payment is already `paid` with amount `300.00`
- **THEN** the system MUST NOT overwrite that amount or billing month via a normal update API

### Requirement: At most one paid delivery fee per customer per calendar month

The system MUST enforce uniqueness of paid delivery-fee collection per customer for a given `(payment_year, payment_month)`. A second successful paid collection for the same customer and month MUST be rejected as a conflict unless it is an idempotent replay of the same deduct request.

#### Scenario: Duplicate month payment rejected

- **WHEN** customer Rahim already has a paid delivery-fee payment for September 2026 and an admin attempts another non-idempotent deduct for September 2026
- **THEN** the system rejects the operation without creating a second paid payment or a second completed debit for that month

#### Scenario: Idempotent replay returns original payment

- **WHEN** the same deduct request is retried with the same `Idempotency-Key` after a successful September 2026 payment
- **THEN** the system does not double-debit and returns the original payment outcome

### Requirement: Delivery fee wallet debit uses a distinct transaction type

Each successful delivery-fee deduction MUST create exactly one completed customer `WalletTransaction` with `type=delivery_fee_payment`, `direction=debit`, and `status=completed`. The transaction MUST NOT use meal-delivery payment typing. The transaction MUST record `balance_after`, a human-readable note naming the billing period (for example `September 2026 Delivery Fee`), and metadata sufficient to recover billing month/year, reason, actor admin identity, and payment public id.

#### Scenario: Wallet history shows delivery fee type

- **WHEN** a delivery fee of `300.00` for September 2026 is deducted successfully
- **THEN** the customer wallet ledger contains a `delivery_fee_payment` debit of `300.00` with note/metadata identifying September 2026

#### Scenario: Meal payment type remains unchanged

- **WHEN** a meal delivery is charged after this capability exists
- **THEN** that meal charge continues to use the existing meal payment transaction type/purpose and is not recorded as `delivery_fee_payment`

### Requirement: Schema supports future automated collection

`DeliveryFeePayment` MUST include a `source` field defaulting to `manual` for Phase 1 admin deducts and MUST allow nullable automation-oriented fields (rule code and/or service-area/metadata) so future automatic generation can reuse the same table without a breaking redesign.

#### Scenario: Manual deduct records source manual

- **WHEN** an admin completes a Phase 1 deduct
- **THEN** the payment row has `source=manual`

### Requirement: Deductions remain auditable and designed for reversal

Every paid delivery-fee payment MUST retain actor admin, customer, amount, billing period, reason, and created timestamp for audit queries. Future reversal MUST NOT edit the original debit amount in place; reversal MUST be modeled as an opposite ledger credit plus an explicit payment status/transition (for example `reversed`) documented for a later change.

#### Scenario: Audit fields present after deduct

- **WHEN** Admin Shohan deducts `300.00` from Rahim for September 2026 with reason `September Delivery Fee`
- **THEN** the payment row stores Shohan as actor, Rahim as customer, amount `300.00`, September 2026 period, the reason, and the deduction timestamp
