## ADDED Requirements

### Requirement: Only verified admins can deduct or inspect delivery fees

The system SHALL expose delivery-fee admin endpoints under the web admin API (`/api/v1/web/...`) and MUST require an authenticated verified admin (`IsVerifiedAdmin`). Unauthenticated callers MUST receive `401`. Authenticated non-admin callers MUST be denied. Customers MUST NOT call admin deduct or admin reporting endpoints.

#### Scenario: Verified admin can access deduct context

- **WHEN** an authenticated verified admin requests delivery-fee context for a customer
- **THEN** the system responds `200` with customer delivery-fee context fields

#### Scenario: Customer cannot deduct delivery fee

- **WHEN** an authenticated customer posts a delivery-fee payment for any customer
- **THEN** the system denies the request and does not change any wallet balance

### Requirement: Admin can load customer delivery-fee deduct context

The system SHALL provide a verified-admin endpoint that returns, for a customer public id: customer display name, phone number, current wallet balance (and bucket balances when already exposed elsewhere), active subscription/package summary when present, and prior delivery-fee payment history (at least recent paid months with amount, status, and paid date).

#### Scenario: Context includes balance and history

- **WHEN** a verified admin opens delivery-fee context for Rahim who has balance `1250.00` and prior paid fees in July and August 2026
- **THEN** the response includes name, phone, wallet balance `1250.00`, and those prior fee payment entries

#### Scenario: Context includes active subscription when present

- **WHEN** the customer has an active subscription package
- **THEN** the context includes that active package/subscription summary

### Requirement: Admin can manually deduct a delivery fee from wallet

The system SHALL allow a verified admin to POST a delivery-fee payment for a customer with required `amount`, `payment_month`, `payment_year`, and `reason`. On success the system MUST atomically: debit the customer wallet by `amount`, create the `delivery_fee_payment` wallet transaction, create the `DeliveryFeePayment` row, and return `201` with payment + updated balance fields. The request SHOULD accept `Idempotency-Key`. Admin Wallet platform cash MUST NOT change as a result of this debit under current custody accounting.

#### Scenario: Successful deduct

- **WHEN** a verified admin deducts `300.00` for September 2026 from a customer with balance `1250.00` and no prior paid September 2026 fee
- **THEN** the system responds `201`, wallet balance becomes `950.00`, and paid payment + wallet debit exist for September 2026

#### Scenario: Processed by admin is recorded

- **WHEN** the deduct succeeds
- **THEN** the payment and/or wallet transaction records identify the acting verified admin

### Requirement: Insufficient balance blocks deduction

When the requested delivery-fee `amount` exceeds the customer’s available wallet balance, the system MUST reject the deduct without changing balance and without creating a completed paid payment. The client-facing error MUST communicate insufficient wallet balance.

#### Scenario: Overdraw prevented

- **WHEN** wallet balance is `200.00` and admin attempts to deduct `300.00`
- **THEN** the system rejects the request, balance remains `200.00`, and no paid delivery-fee payment is created for that attempt

### Requirement: Frozen or inactive wallet cannot be deducted

If the customer wallet is not in an operable `active` status for debits, the system MUST reject the delivery-fee deduct without creating a completed paid payment.

#### Scenario: Frozen wallet rejected

- **WHEN** the customer wallet status is `frozen` and an admin attempts a delivery-fee deduct
- **THEN** the system rejects the deduct and does not create a paid payment

### Requirement: Admin can list a customer’s delivery-fee payments

The system SHALL provide a paginated verified-admin list of delivery-fee payments for a customer ordered newest billing period first (year/month then created/id tie-breaker). Each item MUST include amount, billing month/year, status, paid/created timestamp, and actor admin display identity when available.

#### Scenario: Customer history list

- **WHEN** a verified admin lists delivery-fee payments for a customer with September and August 2026 paid rows
- **THEN** both rows appear with amount, status `paid`, and paid dates

### Requirement: Delivery-fee OpenAPI exists for admin contracts

The system SHALL document all admin delivery-fee context, deduct, list, and related error responses in OpenAPI with stable `operationId`s, auth requirements, request/response schemas, and examples.

#### Scenario: OpenAPI includes deduct endpoint

- **WHEN** a developer inspects the generated OpenAPI schema after this change
- **THEN** the delivery-fee deduct and context operations are present with request body and error responses documented
