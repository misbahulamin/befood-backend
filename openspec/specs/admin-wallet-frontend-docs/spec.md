## Purpose

Frontend and backend documentation for Admin Wallet so Admin Panel and API engineers can integrate and verify without reading source.
## Requirements
### Requirement: Frontend Admin Wallet integration documentation exists
The system SHALL provide frontend documentation at `admin_wallet/docs/frontend/admin-wallet.md` that enables an Admin Panel engineer to implement the Wallet section without reading backend source. The document MUST describe base paths, auth (`IsVerifiedAdmin` / JWT), endpoint grid, request/response field meanings, summary card mapping, deposit/withdraw/expense flows, filter/search query parameters, error cases, and a recommended UI call order.

#### Scenario: Docs cover dashboard and mutations
- **WHEN** a frontend engineer opens the Admin Wallet frontend doc
- **THEN** the doc explains how to load dashboard summaries, render recent transactions, and perform deposit, withdrawal, and expense actions with example payloads

### Requirement: Backend technical documentation exists
The system SHALL provide backend documentation at `admin_wallet/docs/backend/admin-wallet.md` covering models, ledger rules, ingestion hook from meal payment, idempotency keys, permissions, and how to verify via tests or admin API smoke steps.

#### Scenario: Backend doc explains meal-payment credit hook
- **WHEN** a backend engineer opens the Admin Wallet backend doc
- **THEN** the doc states when Admin Wallet is credited from meal delivery charges and how duplicate prevention works

### Requirement: Frontend docs describe profit cards and package breakdown UX
The system SHALL update `admin_wallet/docs/frontend/admin-wallet.md` so an Admin Panel engineer can implement Total Profit and This Month Profit cards on `/admin/wallet` without reading backend source. The document MUST map `total_profit` and `month_profit` to the two cards, MUST state that clicking each card shows the corresponding `profit_by_package.lifetime` or `profit_by_package.month` list, MUST define row columns (package name, charged deliveries, revenue, profit), MUST warn that `month_revenue` is cash income not meal profit, and MUST note that data comes from the existing dashboard endpoint in one response.

#### Scenario: Docs cover profit card click → package breakdown
- **WHEN** a frontend engineer opens the Admin Wallet frontend doc after this change
- **THEN** the doc explains how to render the two profit cards and open a package-wise breakdown from `profit_by_package` without a second API call for v1

### Requirement: Docs explain expense vs customer withdrawal and provider ref reuse
The Admin Wallet and wallet funding documentation MUST state that: (1) dashboard `today_expense` / `month_expense` mean business `EXPENSE_TYPES` only and do not include customer withdraw custody debits; (2) period customer-withdrawal fields (or equivalent documented names) show approved customer payouts; (3) approve withdraw posts Admin Wallet `customer_withdraw` and reduces balance without counting as expense; (4) after a rejected provider recharge (`failed`), the same `transaction_id` may be reused, while pending or completed refs remain blocked. Frontend docs MUST call out the semantic change for expense cards so Admin Panel engineers update labels/mappings.

#### Scenario: Frontend doc distinguishes expense and customer withdrawal
- **WHEN** a frontend engineer opens the Admin Wallet frontend documentation
- **THEN** the doc maps expense cards to expense-typed debits and describes separate customer-withdrawal period totals

#### Scenario: Funding docs describe transaction id reuse after reject
- **WHEN** a frontend or backend engineer reads wallet funding documentation for provider recharge
- **THEN** the doc states that rejected/failed provider transaction ids may be reused and pending/completed ones may not

