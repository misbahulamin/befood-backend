## Purpose

Web admin APIs for BeFood Food Inventory: verified-admin dashboard summaries, low/out-of-stock lists, allowlisted reports, inventory audit log exposure, and OpenAPI-documented routing under the web inventory prefix.

## Requirements

### Requirement: Inventory dashboard summary for verified admins
The system SHALL provide a web inventory dashboard API for verified admins that returns summary metrics including at least: total inventory items, total stock value, today’s purchase count/amount, this month’s purchase cost, low-stock item count, out-of-stock item count, today’s kitchen usage summary, and total wastage summary for a documented period. Access MUST require verified admin authentication; customers MUST be denied.

#### Scenario: Dashboard returns summary cards
- **WHEN** a verified admin calls the inventory dashboard endpoint
- **THEN** the response includes the documented summary fields with decimal monetary values and item counts

#### Scenario: Customer denied dashboard
- **WHEN** a customer calls the inventory dashboard endpoint
- **THEN** the system denies access with `401` or `403`

### Requirement: Low stock and out of stock lists
The system SHALL expose dashboard or list endpoints that identify low-stock items and out-of-stock items using the item-master stock signal rules so purchasing decisions are visible in the Admin Panel.

#### Scenario: Low stock section lists Beef
- **WHEN** Beef is below its minimum stock and still greater than zero
- **THEN** the low-stock list includes Beef

### Requirement: Allowlisted inventory reports
The system SHALL provide verified-admin report endpoints for allowlisted report keys covering at least: daily/weekly/monthly purchase, item-wise purchase, inventory usage, wastage, stock valuation, admin activity, supplier-wise purchase, and expense (inventory purchase) reporting. Unsupported report keys MUST be rejected with `400`. Report responses MUST be paginated or otherwise bounded and MUST use deterministic ordering.

#### Scenario: Monthly purchase report
- **WHEN** a verified admin requests the monthly purchase report for a given month
- **THEN** the system returns purchase aggregates/rows for that month only

#### Scenario: Unknown report key rejected
- **WHEN** a verified admin requests a report key outside the allowlist
- **THEN** the system returns `400` and does not run an unbounded query

### Requirement: Inventory audit log exposure
The system SHALL append audit log entries for important inventory actions including at least: item created, item updated, purchase added, purchase confirmed, purchase cancelled, stock used, stock adjusted, wastage added, invoice uploaded, and wallet deducted for inventory purchase. Each audit entry MUST record acting admin, action, previous/new values when applicable, timestamps, and reference identities. Verified admins MUST be able to list audit logs with allowlisted filters.

#### Scenario: Confirm purchase writes audit entries
- **WHEN** a verified admin confirms a purchase that debits the wallet and adds stock
- **THEN** audit log entries exist for the purchase confirmation and wallet deduction with admin, amounts/quantities, and references

#### Scenario: Stock issue writes audit entry
- **WHEN** a verified admin issues kitchen stock
- **THEN** an audit entry records the admin, item, quantity, previous stock, and new stock

### Requirement: Web routing and OpenAPI documentation
Inventory admin APIs MUST be mounted under `/api/v1/web/inventory/` (or an equivalent documented web inventory prefix), documented in OpenAPI with stable `operationId`s, auth requirements, request/response schemas, and error responses, and MUST follow the project’s pagination and error envelope conventions.

#### Scenario: OpenAPI includes purchase confirm
- **WHEN** the OpenAPI schema is generated
- **THEN** it includes the purchase confirm operation with request/response and error documentation
