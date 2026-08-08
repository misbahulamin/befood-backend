## ADDED Requirements

### Requirement: Inventory APIs return stable error_code values
Inventory web APIs MUST return the project error envelope with a machine-readable `error_code` for domain failures raised by inventory services, without leaking raw database/schema errors for known business cases.

#### Scenario: Insufficient stock
- **WHEN** kitchen usage, wastage, or a negative adjustment would drive on-hand below zero
- **THEN** the API responds with HTTP 422
- **AND** `error_code` is `INSUFFICIENT_STOCK`
- **AND** `message` includes available quantity information

#### Scenario: Insufficient admin wallet balance on purchase confirm
- **WHEN** purchase confirm cannot debit Admin Wallet due to insufficient balance
- **THEN** the API responds with HTTP 422
- **AND** `error_code` is `INSUFFICIENT_WALLET_BALANCE`
- **AND** no stock movement is posted for that confirm attempt

#### Scenario: Duplicate item name
- **WHEN** creating or renaming an item to a name whose normalized form already exists
- **THEN** the API responds with HTTP 422
- **AND** `error_code` is `DUPLICATE_ITEM_NAME`

#### Scenario: Unit change locked after stock activity
- **WHEN** an admin attempts to change `default_unit` after the item has stock movements
- **THEN** the API responds with HTTP 422
- **AND** `error_code` is `UNIT_LOCKED`

#### Scenario: Cancel blocked after stock consumed
- **WHEN** an admin cancels a confirmed purchase but purchased quantity is no longer fully available on-hand
- **THEN** the API responds with HTTP 422
- **AND** `error_code` is `CANCEL_BLOCKED_STOCK_CONSUMED`

### Requirement: Malformed inventory query inputs use HTTP 400
Unsupported filters, unsupported report keys, and structurally invalid inventory query parameters MUST use HTTP 400 with a documented `error_code`.

#### Scenario: Unsupported filter
- **WHEN** a list endpoint receives a filter key outside the allowlist
- **THEN** the API responds with HTTP 400
- **AND** `error_code` is `UNSUPPORTED_FILTER`

#### Scenario: Unsupported report key
- **WHEN** `GET /api/v1/web/inventory/reports/{report_key}/` uses a key outside the allowlist
- **THEN** the API responds with HTTP 400
- **AND** `error_code` is `UNSUPPORTED_REPORT`

### Requirement: Inventory error contract is documented for clients
Backend and frontend inventory docs MUST list the inventory `error_code` values used by Admin Inventory APIs so Admin Panel UI can map operator-facing states.

#### Scenario: Frontend docs cover primary operator codes
- **WHEN** an Admin Panel developer reads `inventory/docs/frontend/admin-inventory.md`
- **THEN** the doc includes at least `INSUFFICIENT_STOCK`, `INSUFFICIENT_WALLET_BALANCE`, `DUPLICATE_ITEM_NAME`, `UNIT_LOCKED`, `CANCEL_BLOCKED_STOCK_CONSUMED`, `UNSUPPORTED_FILTER`, and `UNSUPPORTED_REPORT`
- **AND** each listed code states the expected HTTP status family (400 vs 422)

#### Scenario: Frontend error mapper can distinguish operator cases
- **WHEN** the Admin Panel maps an inventory API error
- **THEN** it MUST be able to detect insufficient stock, insufficient wallet, cancel blocked, duplicate name, unit locked, and unsupported filter/report via `error_code`
- **AND** it MUST display the API `message` (or a safe fallback) without treating schema OperationalErrors as the normal path after repair
