## MODIFIED Requirements

### Requirement: Dashboard provides summary cards and recent transactions
The system SHALL provide a dashboard representation that includes at least: current balance, today’s income, today’s expense, this month’s revenue/income, this month’s expense, total customer payments, and total withdrawn. The dashboard MUST also include a recent transactions list (bounded/paginated) ordered newest first. Period fields named `today_expense` and `month_expense` MUST sum only completed Admin Wallet debits whose `type` is in `EXPENSE_TYPES` (business expense categories). Those period expense fields MUST NOT include `customer_withdraw` or admin `withdrawal` debits. The dashboard MUST also expose period customer-withdrawal totals (for today and this month) derived from completed `customer_withdraw` debits so clients can display custody outflows separately from business expense.

#### Scenario: Dashboard returns period aggregates
- **WHEN** a verified admin requests the Admin Wallet dashboard after completed credits and debits exist today and this month
- **THEN** the response includes current balance and the required today/month/lifetime summary fields plus recent transactions

#### Scenario: Customer withdraw does not inflate period expense
- **WHEN** a completed `customer_withdraw` debit of `200.00` is the only Admin Wallet debit today and no expense-typed debits exist today
- **THEN** `today_expense` is `0.00` and today’s customer-withdrawal period total is `200.00`

#### Scenario: Operational expense still counts as period expense
- **WHEN** a completed `operational_expense` debit of `50.00` exists today
- **THEN** `today_expense` includes `50.00`
