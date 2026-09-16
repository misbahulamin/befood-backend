## MODIFIED Requirements

### Requirement: Frontend Admin Wallet integration documentation exists
The system SHALL provide frontend documentation at `admin_wallet/docs/frontend/admin-wallet.md` that enables an Admin Panel engineer to implement the Wallet section without reading backend source. The document MUST describe base paths, auth (`IsVerifiedAdmin` / JWT), endpoint grid, request/response field meanings, summary card mapping, deposit/withdraw/expense flows, filter/search query parameters, error cases, and a recommended UI call order. The document MUST clarify that customer withdraw approve reduces platform cash via `customer_withdraw`, that `total_customer_funding` is a lifetime inflow counter, and that remaining customer custody should use net funding (`total_customer_funding - total_customer_withdrawals` / `net_customer_funding`). Customer funding approve screens that review personal-wallet withdraws MUST document showing balance before, withdraw amount, remaining balance, and meal-stop context when provided by the funding APIs.

#### Scenario: Docs cover dashboard and mutations
- **WHEN** a frontend engineer opens the Admin Wallet frontend doc
- **THEN** the doc explains how to load dashboard summaries, render recent transactions, and perform deposit, withdrawal, and expense actions with example payloads

#### Scenario: Docs explain customer funding vs withdraw counters
- **WHEN** a frontend engineer reads the Admin Wallet summary field guide
- **THEN** the doc states not to expect `total_customer_funding` to fall on customer withdraw and to display net custody and/or `today_customer_withdrawals` separately from business expense
