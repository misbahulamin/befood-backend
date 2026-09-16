## MODIFIED Requirements

### Requirement: Frontend Admin Wallet integration documentation exists
The system SHALL provide frontend documentation at `admin_wallet/docs/frontend/admin-wallet.md` that enables an Admin Panel engineer to implement the Wallet section without reading backend source. The document MUST describe base paths, auth (`IsVerifiedAdmin` / JWT), endpoint grid, request/response field meanings, summary card mapping, deposit/withdraw/expense flows, filter/search query parameters, error cases, and a recommended UI call order. The document MUST state that meal profit cards are **not** served by the wallet dashboard and MUST link or point to the Admin Profit frontend documentation for profit analytics.

#### Scenario: Docs cover dashboard and mutations without profit fields
- **WHEN** a frontend engineer opens the Admin Wallet frontend doc
- **THEN** the doc explains how to load dashboard summaries, render recent transactions, and perform deposit, withdrawal, and expense actions with example payloads, and does not instruct the client to read `total_profit` / `month_profit` / `profit_by_package` from the wallet dashboard

## REMOVED Requirements

### Requirement: Frontend docs describe profit cards and package breakdown UX
**Reason:** Profit UX moves to dedicated Admin Profit APIs and docs.
**Migration:** Implement profit cards, package breakdown, meal-period split, and daily charts using `admin_wallet/docs/frontend/` Admin Profit documentation and `GET /api/v1/web/admin-profit/*` endpoints.

## ADDED Requirements

### Requirement: Frontend docs describe migration from wallet profit fields
The system SHALL document the breaking removal of wallet-dashboard profit fields and the replacement Admin Profit endpoints so Admin Panel can migrate without reading backend source.

#### Scenario: Docs explain breaking profit field removal
- **WHEN** a frontend engineer reads Admin Wallet or Admin Profit frontend docs after this change
- **THEN** the docs explicitly list removed wallet fields and show the replacement profit dashboard/history calls
