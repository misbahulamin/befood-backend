## ADDED Requirements

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
