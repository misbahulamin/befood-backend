## ADDED Requirements

### Requirement: Inventory schema matches current models
The system MUST have physical inventory tables and columns that match the current `inventory` Django models, including `InventoryItem.name_normalized`, `InventoryItem.status`, and related purchase/ledger tables.

#### Scenario: Dashboard reads items without OperationalError
- **WHEN** a verified admin calls `GET /api/v1/web/inventory/dashboard/`
- **THEN** the response is not an HTTP 500 caused by missing inventory columns
- **AND** the handler can query `InventoryItem` fields defined on the current model

#### Scenario: Item list filters by status
- **WHEN** a verified admin calls `GET /api/v1/web/inventory/items/?status=active`
- **THEN** the database query uses an existing `status` column on `inventory_inventoryitem`
- **AND** the response is a successful paginated list (possibly empty)

#### Scenario: Item create uses name_normalized uniqueness
- **WHEN** a verified admin creates an item via `POST /api/v1/web/inventory/items/`
- **THEN** the service can read/write `name_normalized` without `OperationalError`
- **AND** duplicate normalized names return a business error, not a database schema error

### Requirement: Recover from fake-applied inventory migrations
When Django records inventory migrations as applied but the physical schema is the superseded legacy inventory shape (or incomplete), the project MUST provide a repair path that rebuilds the schema from the current inventory migration(s).

#### Scenario: Detect legacy mismatch
- **WHEN** `inventory_inventoryitem` exists without `name_normalized` (or required purchase/ledger tables are missing)
- **THEN** the repair tooling MUST treat the schema as mismatched
- **AND** MUST NOT claim the inventory app is healthy solely because `django_migrations` shows the new migration as applied

#### Scenario: Safe repair on empty local tables
- **WHEN** a developer runs the inventory schema repair path and all inventory tables are empty
- **THEN** the system drops obsolete inventory tables, clears stale `inventory` rows from `django_migrations`, and applies the current inventory migration(s) for real
- **AND** afterward `InventoryItem` has the columns required by the current models

#### Scenario: Refuse destructive repair when data exists
- **WHEN** a developer runs the default inventory schema repair path and any inventory table has one or more rows
- **THEN** the command MUST abort without dropping tables
- **AND** it MUST require an explicit force flag (or equivalent) before destructive rebuild
