## Purpose

Canonical minimum recharge amount: storage, admin editing, and backend enforcement.

## Requirements

### Requirement: Canonical field
The system SHALL store `minimum_recharge_amount` on the `OrderWalletSettings` singleton as Decimal(12,2) with default `500.00` and non-negative (≥ 0, ≤ 2 decimal places) validation.

#### Scenario: Default value
- WHEN the singleton is loaded with no prior value THEN `minimum_recharge_amount` SHALL equal `500.00`.

### Requirement: Admin editing
The system SHALL allow verified admins to read/update `minimum_recharge_amount` via the existing order-wallet-settings GET/PATCH; unauthorized callers SHALL be denied; invalid (negative / >2dp / non-numeric) values SHALL be rejected with 400.

#### Scenario: Admin raises 500 → 700
- WHEN admin PATCHes `{"minimum_recharge_amount": "700.00"}` THEN subsequent `request_recharge(600)` SHALL be rejected and `request_recharge(700)` SHALL succeed.

### Requirement: Backend enforcement boundary
The system SHALL reject recharge requests with `amount < minimum` and accept `amount == minimum` and `amount > minimum`, using Decimal comparison (never float).

#### Scenario: Boundary at 500
- WHEN minimum is `500.00` THEN `499.99` SHALL be rejected, `500.00` SHALL create PENDING, `500.01` SHALL create PENDING.

#### Scenario: Error contract
- WHEN rejected for minimum THEN response SHALL be HTTP 400 with `code=RECHARGE_BELOW_MINIMUM`, human `detail` naming the current minimum, and `minimum_recharge_amount` string.

### Requirement: Existing data untouched
The system SHALL NOT retroactively invalidate or modify existing PENDING/COMPLETED/FAILED recharge rows when the setting changes; the check SHALL apply only inside `request_recharge` for new requests.
