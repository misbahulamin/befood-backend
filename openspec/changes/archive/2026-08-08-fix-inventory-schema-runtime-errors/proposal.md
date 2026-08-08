## Why

Admin Inventory APIs are returning HTTP 500 (`OperationalError: no such column …`) because the local SQLite schema still matches an older inventory rewrite (`slug` / `kind` / `is_active`), while Django code and migration `inventory.0001_inventory_and_wallet_types` expect the new ledger models (`name_normalized`, `status`, purchases, etc.). The new migration is recorded as applied, so `migrate` is a no-op and the Admin Panel Inventory UI cannot load dashboard, list items, or create items. Error-code HTTP mapping and frontend handling are also incomplete for several business failures already raised by services.

## What Changes

- Repair the inventory database schema so it matches current models (drop obsolete empty legacy tables / stale migration records; apply the current inventory initial migration for real).
- Add a repeatable **dev/local schema repair** path (management command or documented migrate steps) so fake/stale migration state cannot silently leave APIs broken.
- Harden inventory API error responses: map business-rule `error_code` values to correct HTTP status (prefer `422` for validation/business rules; keep `400` for malformed/unsupported filters).
- Complete the inventory `error_code` contract in backend + frontend docs (all codes services already emit).
- Plan sibling **befood-frontend** updates so `mapInventoryError` and forms handle the full code set (unit lock, invalid status, cancel blocked already partial, etc.) without treating schema 500s as generic failures.
- Re-run inventory tests after schema repair to confirm dashboard/items/purchases work end-to-end.

## Capabilities

### New Capabilities
- `inventory-schema-repair`: Ensure Django migration state and physical inventory tables match the current `InventoryItem` / purchase / ledger models; recover from fake-applied or superseded `0001_initial` schemas safely when tables are empty (or document destructive reset for local only).
- `inventory-error-contract`: Stable inventory `error_code` → HTTP status mapping and documented client-facing codes for Admin Inventory APIs and Admin Panel UI.

### Modified Capabilities
- _(none in `openspec/specs/`)_ — prior inventory requirements live only under `openspec/changes/food-inventory-system/` and are not archived to main specs yet.

## Impact

- **Backend DB**: `db.sqlite3` inventory tables; `django_migrations` rows for `inventory` (`0001_initial` stale + `0001_inventory_and_wallet_types` fake-applied).
- **Backend code**: `inventory/api/views.py` (`_error_response`), possibly a small management command under `inventory/management/commands/`, docs under `inventory/docs/{backend,frontend}/`.
- **Tests**: `inventory/tests/test_inventory.py` must pass against a repaired schema.
- **Frontend** (`F:\befood\befood-frontend`): Admin Inventory pages already call `/api/v1/web/inventory/`; update error mapping / UX for codes not yet surfaced (`UNIT_LOCKED`, `INVALID_STATUS`, `PURCHASE_CANCELLED`, unit errors, etc.). No API URL changes expected if schema repair restores the existing contract.
- **Admin Wallet**: no schema change required (`0004_inventory_and_wallet_types` already applied and matches models).
- **Non-goals**: redesigning inventory domain models; production data migration from the old `slug`/`kind` schema (local DB has 0 inventory rows); mobile inventory routes.
