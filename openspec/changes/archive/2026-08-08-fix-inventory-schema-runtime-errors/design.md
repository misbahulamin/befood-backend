## Context

Observed production of the bug on local SQLite (`db.sqlite3`):

| Layer | State |
|-------|--------|
| Models / services / APIs | New inventory rewrite (`name_normalized`, `status`, purchases, ledger tables) |
| Migration file | `inventory/migrations/0001_inventory_and_wallet_types.py` (creates full new schema) |
| `django_migrations` | Both `inventory.0001_initial` (2026-07-26) **and** `inventory.0001_inventory_and_wallet_types` (2026-08-08, recorded applied) |
| Physical tables | Legacy only: `inventory_inventoryitem` (`slug`, `kind`, `unit`, `is_active`, …) and `inventory_stockmovement` (old shape); **0 rows** |
| Missing tables | purchases, lines, kitchen usage, wastage, adjustment, audit log, new stock movement |

Runtime failures from the Admin Panel:

1. `GET /api/v1/web/inventory/dashboard/` → `no such column: …name_normalized`
2. `POST /api/v1/web/inventory/items/` → same
3. `GET /api/v1/web/inventory/items/?status=active` → `no such column: …status`

`makemigrations` / `migrate --plan` report nothing pending because Django trusts the fake-applied new migration.

Secondary issue: `_error_response` defaults almost all `InventoryError` / `InventoryUnitError` codes to HTTP 400. API guidelines prefer **422** for structurally valid but business-invalid input. Frontend `mapInventoryError` only special-cases a subset of codes.

Stakeholders: backend (schema + error contract), Admin Panel frontend (`befood-frontend` inventory feature).

## Goals / Non-Goals

**Goals:**

- Restore a schema that matches current inventory models so dashboard/items/purchases stop 500ing.
- Make local recovery safe and repeatable (empty legacy tables → rebuild).
- Align HTTP status + documented `error_code` set with what services already raise.
- Document / plan frontend updates for the full error contract (sibling repo).

**Non-Goals:**

- Changing inventory domain model fields or wallet debit semantics.
- Migrating non-empty legacy inventory data (none present locally; prod path deferred if ever needed).
- Archiving `food-inventory-system` into main OpenSpec specs.
- Implementing frontend code inside this backend-only apply unless user asks for a cross-repo apply.

## Decisions

### 1. Schema repair strategy: drop legacy empty tables + unfake + remigrate (local)

**Choice:** For local/dev SQLite when inventory tables are empty or confirmed disposable:

1. Drop all `inventory_*` tables (and SQLite indexes/FKs as needed).
2. Delete stale `django_migrations` rows for app `inventory` (`0001_initial` and fake `0001_inventory_and_wallet_types`).
3. Run `python manage.py migrate inventory` so `0001_inventory_and_wallet_types` creates the real schema.
4. Verify columns via `PRAGMA table_info` / a smoke GET dashboard.

**Alternatives considered:**

- Hand-written `ALTER TABLE` migration from old → new: high risk, old model is incompatible (different columns/table set); not worth it with 0 rows.
- Delete entire `db.sqlite3`: works but wipes unrelated local data (users, wallet); too blunt as default.
- Only `--fake` reverse: leaves broken tables in place.

**Rationale:** Empty tables + rewrite migration already exists → recreate is the correct fix.

### 2. Ship a management command `repair_inventory_schema`

**Choice:** Add `python manage.py repair_inventory_schema` that:

- Detects mismatch (e.g. missing `name_normalized` or missing `inventory_inventorypurchase`).
- Refuses to drop when any inventory table has rows unless `--force` (or `--force-empty-only` default).
- Performs drop + migration record cleanup + migrate for the inventory app.
- Prints before/after column list.

**Alternatives:** Docs-only SQL steps — easy to mistype; command encodes the safety check.

### 3. Error HTTP mapping in `_error_response`

**Choice:** Classify codes:

| HTTP | Codes |
|------|--------|
| 422 | `INSUFFICIENT_STOCK`, `INSUFFICIENT_WALLET_BALANCE`, `DUPLICATE_ITEM_NAME`, `INVALID_STATUS`, `INVALID_MINIMUM_STOCK`, `INVALID_QUANTITY`, `INVALID_AMOUNT`, `INVALID_UNIT`, `UNSUPPORTED_UNIT`, `INCOMPATIBLE_UNIT`, `UNIT_LOCKED`, `NAME_REQUIRED`, `ITEM_REQUIRED`, `LINES_REQUIRED`, `REASON_REQUIRED`, `PURCHASE_CANCELLED`, `INVALID_PURCHASE_STATUS`, `CANCEL_BLOCKED_STOCK_CONSUMED`, `ADMIN_WALLET_ERROR` (when wrapped from wallet business errors) |
| 400 | `UNSUPPORTED_FILTER`, `UNSUPPORTED_REPORT`, `INVOICE_REQUIRED`, `INVALID_INVOICE_TYPE`, `INVOICE_TOO_LARGE`, malformed query parsing |
| 404 | `NOT_FOUND`, `ITEM_NOT_FOUND` (already returned outside helper in places) |

Keep response body shape unchanged: `{ success, message, errors, error_code }`.

**Alternatives:** Leave all as 400 — simpler but conflicts with API guidelines and existing frontend expectations for 422 on stock/wallet.

### 4. Frontend plan (sibling `befood-frontend`)

**Choice:** Backend docs list the full code table; frontend tasks (manual in that repo):

- Extend `mapInventoryError` flags for `UNIT_LOCKED`, `INVALID_STATUS`, `PURCHASE_CANCELLED`, unit incompatibility, `INVALID_MINIMUM_STOCK`.
- Surface field-level toast/banner on item create/edit and purchase confirm/cancel.
- After backend repair, smoke: dashboard load, create item, list `?status=active`, confirm purchase.

No URL/path changes expected.

### 5. Docs

Update `inventory/docs/backend/admin-inventory.md` and `inventory/docs/frontend/admin-inventory.md` error tables to match the mapping above; mention repair command for local setup.

## Risks / Trade-offs

- **[Risk] Someone runs repair against a DB with legacy inventory rows** → Mitigation: command aborts unless empty or `--force`; document that force is destructive.
- **[Risk] Other environments also faked the migration** → Mitigation: same command; CI/test DB usually creates schema via migrate from scratch (already green if migrations never faked).
- **[Risk] Changing 400→422 breaks a frontend that keys only on status** → Mitigation: frontend already uses `error_code` heavily; stock/wallet already expect 422; expanding 422 is compatible with `mapInventoryError`.
- **[Trade-off] Repair command is SQLite/dev oriented** → Postgres prod with empty tables can still drop/recreate via the same logic if needed; non-empty prod would need a dedicated data migration (out of scope).

## Migration Plan

1. Stop using broken schema (dev server can stay up; next request after repair succeeds).
2. Run `repair_inventory_schema` (or manual drop + migrate steps).
3. Deploy/code: error-mapping + docs + tests.
4. Frontend: pull docs / apply error-map PR after backend is healthy.
5. Rollback: restore SQLite backup if taken; or re-run migrate from backup DB file. No API version bump.

## Open Questions

- None blocking apply: local tables are empty; repair path is clear.
- If a non-local environment has legacy inventory data under the old schema, pause and write a one-off data migration before dropping tables.
