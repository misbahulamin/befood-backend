## ADDED Requirements

### Requirement: Frontend docs describe profit cards and package breakdown UX
The system SHALL update `admin_wallet/docs/frontend/admin-wallet.md` so an Admin Panel engineer can implement Total Profit and This Month Profit cards on `/admin/wallet` without reading backend source. The document MUST map `total_profit` and `month_profit` to the two cards, MUST state that clicking each card shows the corresponding `profit_by_package.lifetime` or `profit_by_package.month` list, MUST define row columns (package name, charged deliveries, revenue, profit), MUST warn that `month_revenue` is cash income not meal profit, and MUST note that data comes from the existing dashboard endpoint in one response.

#### Scenario: Docs cover profit card click → package breakdown
- **WHEN** a frontend engineer opens the Admin Wallet frontend doc after this change
- **THEN** the doc explains how to render the two profit cards and open a package-wise breakdown from `profit_by_package` without a second API call for v1
