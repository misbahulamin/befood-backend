## Purpose

Verified-admin mutations on the Admin Wallet: manual deposit, withdrawal with balance guard, typed platform expenses, and audit logging for sensitive operations.

## Requirements

### Requirement: Verified admin can manually deposit into Admin Wallet
The system SHALL allow an authorized verified admin to post a manual deposit that credits the Admin Wallet. The request MUST include a positive amount and SHOULD include reason/note as required by the API contract. The resulting ledger entry MUST use type `manual_deposit`, direction `credit`, status `completed`, record the acting admin, and appear in transaction history.

#### Scenario: Manual deposit increases balance
- **WHEN** a verified admin posts a manual deposit of `100000.00` with a reason
- **THEN** the Admin Wallet balance increases by `100000.00` and a completed `manual_deposit` credit of `100000.00` exists with the acting admin recorded

#### Scenario: Non-positive deposit is rejected
- **WHEN** a verified admin posts a deposit with amount `0` or negative
- **THEN** the system rejects the request and does not change the Admin Wallet balance

### Requirement: Verified admin can withdraw from Admin Wallet with balance guard
The system SHALL allow an authorized verified admin to withdraw funds from the Admin Wallet when the amount is positive and less than or equal to available balance. Withdrawal MUST require a reason. The ledger entry MUST use type `withdrawal`, direction `debit`, status `completed`, and reduce the balance atomically.

#### Scenario: Withdrawal within balance succeeds
- **WHEN** the Admin Wallet balance is `50000.00` and a verified admin withdraws `25000.00` with reason `Operational Expense`
- **THEN** the balance becomes `25000.00` and a completed `withdrawal` debit of `25000.00` exists

#### Scenario: Withdrawal above balance is rejected
- **WHEN** the Admin Wallet balance is `50000.00` and a verified admin attempts to withdraw `60000.00`
- **THEN** the system rejects the withdrawal, creates no completed withdrawal debit, and leaves the balance unchanged

### Requirement: Verified admin can post typed platform expenses
The system SHALL allow an authorized verified admin to post debit expenses with an allowlisted expense type, including at least: `customer_refund`, `restaurant_settlement`, `rider_payment`, `operational_expense`, `onahar_expense`, `promotional_cost`, `platform_expense`, and `manual_adjustment`. Expense posting MUST enforce available balance, require reason/note per API contract, create a completed debit ledger row, and support optional reference links (order/customer) when provided.

#### Scenario: Rider settlement expense debits wallet
- **WHEN** a verified admin posts a `rider_payment` expense of `5000.00` with a reason and sufficient balance
- **THEN** the Admin Wallet decreases by `5000.00` and a completed `rider_payment` debit exists in history

#### Scenario: Unknown expense type is rejected
- **WHEN** a verified admin posts an expense with a type outside the allowlist
- **THEN** the system rejects the request and does not change the balance

### Requirement: Sensitive operations write audit records
The system SHALL append an audit log entry for manual deposit, withdrawal, expense posting, and balance adjustment operations. Each audit entry MUST record acting admin, action, amount, previous balance, new balance, reason, related transaction identity when applicable, and timestamps.

#### Scenario: Withdrawal creates audit log
- **WHEN** a verified admin completes a withdrawal
- **THEN** an audit log entry exists showing the admin, withdrawal action, amount, previous balance, new balance, and reason
