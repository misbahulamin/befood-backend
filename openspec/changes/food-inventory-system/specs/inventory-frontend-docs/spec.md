## ADDED Requirements

### Requirement: Frontend inventory integration documentation
The system SHALL ship Admin Panel frontend documentation at `inventory/docs/frontend/admin-inventory.md` (or equivalent path under the inventory app) that explains how to build the Inventory section without prior backend knowledge. The document MUST include: base path and auth headers, permission expectations, endpoint grid, field meanings, recommended call order for purchase and kitchen usage flows, dashboard card mapping, filter query parameters, invoice upload usage, wallet insufficient-balance and insufficient-stock error handling, and links to related Admin Wallet docs for cross-navigation.

#### Scenario: Docs describe purchase confirm flow
- **WHEN** a frontend engineer reads the inventory frontend docs
- **THEN** the docs explain create purchase → optional invoice upload → confirm, including wallet debit side effects and error codes

#### Scenario: Docs map dashboard cards to API fields
- **WHEN** a frontend engineer implements the inventory dashboard
- **THEN** the docs map each summary card to a response field from the dashboard endpoint

### Requirement: Frontend docs cover histories and item detail
The frontend documentation MUST describe purchase history, usage history, and item detail pages including how to render movement history (`+qty | type | admin`), low/out-of-stock badges, valuation fields, and links to view related wallet transactions from a purchase.

#### Scenario: Docs explain wallet cross-link
- **WHEN** a frontend engineer implements purchase detail
- **THEN** the docs state which response field holds the wallet transaction reference and how to open Admin Wallet transaction detail
