## ADDED Requirements

### Requirement: Customer withdraw is custody release not business expense
When a customer wallet withdraw completes successfully and the Admin Wallet is debited, the system MUST post exactly one completed Admin Wallet transaction of type `customer_withdraw` (direction `debit`) for that customer wallet transaction. The debit MUST reduce Admin Wallet available balance and MUST increment `total_customer_withdrawals`. The system MUST NOT create an expense-typed Admin Wallet transaction for that withdraw and MUST NOT increment `total_expenses` solely because of that withdraw.

#### Scenario: Withdraw approve posts customer_withdraw not expense
- **WHEN** an admin approves a pending customer withdraw of `200.00` and Admin Wallet float covers the amount
- **THEN** the Admin Wallet balance decreases by `200.00`, exactly one completed `customer_withdraw` debit of `200.00` exists for that customer wallet transaction, and lifetime `total_expenses` is unchanged by that debit

#### Scenario: Withdraw approve does not use expense ledger types
- **WHEN** an admin approves a customer withdraw
- **THEN** no Admin Wallet row of type in `EXPENSE_TYPES` is created for that approval event
