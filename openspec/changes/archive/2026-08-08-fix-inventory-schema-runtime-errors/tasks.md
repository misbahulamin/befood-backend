## 1. Diagnose and repair local schema

- [x] 1.1 Confirm mismatch on this machine: `PRAGMA table_info(inventory_inventoryitem)` missing `name_normalized`/`status`, and `django_migrations` has both `0001_initial` and fake-applied `0001_inventory_and_wallet_types`
- [x] 1.2 Add `inventory/management/commands/repair_inventory_schema.py` that detects mismatch, aborts if inventory tables have rows (unless `--force`), drops `inventory_*` tables, deletes `django_migrations` rows for app `inventory`, then runs `migrate inventory`
- [x] 1.3 Run the repair command against local `db.sqlite3` and verify new columns/tables exist (`name_normalized`, `status`, `inventory_inventorypurchase`, etc.)
- [x] 1.4 Smoke-check with the running server: `GET /dashboard/`, `GET /items/?status=active`, `POST /items/` no longer return OperationalError 500

## 2. Harden inventory error HTTP mapping

- [x] 2.1 Update `inventory/api/views.py` `_error_response` to map business codes to HTTP 422 (stock/wallet/duplicate/unit/status/quantity/cancel-blocked/etc.) and keep filter/report/invoice structural issues at 400
- [x] 2.2 Ensure `InventoryUnitError` codes (`UNSUPPORTED_UNIT`, `INCOMPATIBLE_UNIT`, `INVALID_QUANTITY`, `INVALID_UNIT`) flow through the same mapping
- [x] 2.3 Add or extend API tests covering at least: duplicate name → 422/`DUPLICATE_ITEM_NAME`, unsupported filter → 400/`UNSUPPORTED_FILTER`, insufficient stock → 422/`INSUFFICIENT_STOCK` (reuse existing coverage where present)

## 3. Docs (backend + frontend contract)

- [x] 3.1 Expand `inventory/docs/backend/admin-inventory.md` error table with the full code → HTTP map and note the repair command for local setup
- [x] 3.2 Expand `inventory/docs/frontend/admin-inventory.md` with operator-facing codes (`DUPLICATE_ITEM_NAME`, `UNIT_LOCKED`, `CANCEL_BLOCKED_STOCK_CONSUMED`, unit errors, etc.) and UI handling notes
- [x] 3.3 Document recommended local recovery steps in backend docs (backup optional → repair → re-test)

## 4. Frontend plan (`F:\befood\befood-frontend` — implement in that repo)

- [x] 4.1 Extend `mapInventoryError` in `src/features/admin/utils/adminInventoryLabels.ts` with flags for `UNIT_LOCKED`, `INVALID_STATUS`, `PURCHASE_CANCELLED`, `INCOMPATIBLE_UNIT` / `UNSUPPORTED_UNIT`, `INVALID_MINIMUM_STOCK`
- [x] 4.2 Wire item form / purchase confirm-cancel / stock issue UIs to show those mapped states (toast or inline) using API `message`
- [x] 4.3 After backend repair, smoke Admin Inventory: dashboard cards load, create item, list active items, draft+confirm purchase, kitchen issue insufficient-stock path
- [x] 4.4 No route/base-path changes unless backend docs introduce new endpoints (none expected)

## 5. Verification

- [x] 5.1 Run `python manage.py test inventory.tests.test_inventory`
- [x] 5.2 Run `python manage.py check` and confirm `migrate --plan` has no pending inventory ops after repair
- [x] 5.3 Confirm Admin Panel Inventory page no longer shows 500 on dashboard/items
