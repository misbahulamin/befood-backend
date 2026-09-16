## Purpose

Web admin APIs for the BeFood platform Admin Wallet: auth-gated summary, dashboard aggregates, filtered transaction history, typed ledger categories, and audit log reads.
## Requirements
### Requirement: Only verified admins can access Admin Wallet APIs
The system SHALL expose Admin Wallet management endpoints under the web admin API prefix and MUST require an authenticated verified admin. Unauthenticated callers MUST receive `401`. Authenticated non-admin or unverified admin callers MUST receive `403` (or `404` when concealing existence is required by project policy). Customers and normal users MUST NOT access Admin Wallet data or mutations.

#### Scenario: Verified admin can read wallet summary
- **WHEN** an authenticated verified admin requests the Admin Wallet summary
- **THEN** the system responds `200` with balance and configured summary fields

#### Scenario: Customer cannot access Admin Wallet
- **WHEN** an authenticated verified customer requests an Admin Wallet endpoint
- **THEN** the system denies access and does not return platform wallet data

#### Scenario: Unauthenticated request is rejected
- **WHEN** an unauthenticated client requests an Admin Wallet endpoint
- **THEN** the system responds `401 Unauthorized`

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

### Requirement: Transaction history supports filter and search
The system SHALL provide paginated Admin Wallet transaction history ordered newest first. Each transaction MUST expose at least: public transaction id, type, amount, credit/debit direction, source/reference, order id when present, customer id when present, admin id when present, payment method, note, date/time timestamps, and status. The list MUST support allowlisted filters for date range, direction, transaction type (or documented type groups such as customer payment, manual deposit, withdrawal, refund, expense), payment method, and status. The list MUST support search by transaction public id and allowlisted order/customer identifiers via `q` or equivalent documented parameter. Unsupported filters MUST be rejected with `400`.

#### Scenario: Filter by debit withdrawals
- **WHEN** a verified admin lists transactions filtered to type `withdrawal` (or debit withdrawals)
- **THEN** the response includes only matching withdrawal transactions for the Admin Wallet

#### Scenario: Search by transaction public id
- **WHEN** a verified admin searches history with a known transaction `public_id`
- **THEN** the matching transaction is returned

#### Scenario: Unsupported filter is rejected
- **WHEN** a verified admin supplies an unsupported filter field or operator
- **THEN** the system responds `400 Bad Request`

### Requirement: Transaction types are categorized for credit and debit
The system MUST persist and return documented transaction types covering credit categories (`customer_payment`, `manual_deposit`, `adjustment`, `refund_reversal`, `other_income`) and debit categories (`withdrawal`, `customer_refund`, `restaurant_settlement`, `rider_payment`, `operational_expense`, `onahar_expense`, `promotional_cost`, `platform_expense`, `manual_adjustment`). Clients MUST be able to rely on these string enums for filtering and display.

#### Scenario: Customer payment appears as credit type
- **WHEN** an automatic meal-payment credit is listed in history
- **THEN** its type is `customer_payment` and direction is `credit`

### Requirement: Audit logs are readable by verified admins
The system SHALL provide a paginated Admin Wallet audit log endpoint for verified admins, ordered newest first, exposing actor, action, amount, previous balance, new balance, reason, and timestamps.

#### Scenario: Admin lists audit logs after deposit
- **WHEN** a verified admin completed a manual deposit and requests audit logs
- **THEN** the response includes an audit entry for that deposit with previous and new balances

### Requirement: Dashboard includes meal profit summary and package breakdown
The system SHALL extend the Admin Wallet dashboard representation with additive fields `total_profit`, `month_profit`, and `profit_by_package` (with `lifetime` and `month` package rows) in addition to existing cash and meal-revenue summary cards. Existing dashboard fields (`today_income`, `month_revenue`, funding/withdrawal totals, `recent_transactions`, etc.) MUST remain available and MUST retain their current meanings. Access control for the dashboard MUST remain verified-admin only.

#### Scenario: Dashboard returns profit fields with existing cards
- **WHEN** a verified admin requests the Admin Wallet dashboard after charged meal deliveries and cash credits exist
- **THEN** the response includes the existing balance/today/month cash fields and also `total_profit`, `month_profit`, and `profit_by_package`

#### Scenario: Non-admin still denied after profit fields added
- **WHEN** an authenticated customer requests the Admin Wallet dashboard
- **THEN** the system denies access and does not return profit or wallet data

