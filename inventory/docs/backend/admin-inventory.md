# Food Inventory (Backend)

## Quick summary

Ledger-based kitchen stock system: item master, purchases (Admin Wallet debit), kitchen usage, wastage, adjustments, valuation (WAC), dashboard, and audit.

| Concern | Detail |
|--------|--------|
| App | `inventory` |
| Base path | `/api/v1/web/inventory/` |
| Auth | Token + `IsVerifiedAdmin` |
| Money / qty | Decimal BDT and quantity (no floats) |
| Wallet | Confirm purchase → `inventory_purchase` debit; cancel → `inventory_purchase_reversal` credit |

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin | Full inventory APIs |
| Customer / anonymous | Denied (`401`/`403`) |

## Key models

- **InventoryItem** — stock SKU (`name`, `default_unit`, `category`, `status`, `minimum_stock_level`, `quantity_on_hand`, `average_unit_cost`, optional `linked_ingredient`).
- **InventoryPurchase** / **InventoryPurchaseLine** — draft → confirmed → cancelled; invoice file; wallet txn links.
- **InventoryStockMovement** — append-only ledger (`purchase`, `kitchen_usage`, `wastage`, `adjustment`, `purchase_reversal`).
- **InventoryKitchenUsage** / **InventoryWastage** / **InventoryAdjustment** — typed operation records.
- **InventoryAuditLog** — admin activity trail.

Stock signals (read-only): `out_of_stock` when on-hand ≤ 0; `low_stock` when min set and `0 < on-hand ≤ min`.

## Ledger rules

1. All quantity changes go through `apply_stock_movement` with `select_for_update` on the item.
2. Negative on-hand is rejected (`INSUFFICIENT_STOCK`).
3. Purchases add quantity and update weighted average cost (WAC).
4. Usage/wastage reduce quantity without changing WAC.
5. `quantity_on_hand` must equal Σ movement deltas (`reconcile_inventory_stock` command).

## Purchase + wallet atomicity

On confirm (same `transaction.atomic()`):

1. Debit Admin Wallet (`debit_for_inventory_purchase`, idempotency `inventory-purchase:{public_id}`).
2. Post purchase stock movements + WAC.
3. Link `purchase.wallet_transaction`.

If wallet balance is insufficient → `INSUFFICIENT_WALLET_BALANCE`; no stock change.

Cancel confirmed purchase only when each line’s purchased base qty is still available on-hand; posts `purchase_reversal` movements and wallet credit `inventory_purchase_reversal`.

## Units

Allowlisted: `kg`, `g`, `l`, `ml`, `piece`, `packet`, `box`, `bottle`, `bag`.  
Convertible pairs only: `g`↔`kg`, `ml`↔`l` (factor 1000). Stock stored in item `default_unit`.

## Endpoint grid

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/web/inventory/dashboard/` | Summary cards |
| GET/POST | `/api/v1/web/inventory/items/` | List / create items |
| GET/PATCH | `/api/v1/web/inventory/items/{public_id}/` | Detail (+ history summary) / update |
| GET | `/api/v1/web/inventory/items/{public_id}/movements/` | Movement history |
| GET/POST | `/api/v1/web/inventory/purchases/` | History / create (`confirm` optional) |
| GET | `/api/v1/web/inventory/purchase-history/` | Alias of purchase list |
| GET | `/api/v1/web/inventory/purchases/{public_id}/` | Purchase detail |
| POST | `/api/v1/web/inventory/purchases/{public_id}/confirm/` | Confirm + wallet debit |
| POST | `/api/v1/web/inventory/purchases/{public_id}/cancel/` | Cancel / reverse |
| POST | `/api/v1/web/inventory/purchases/{public_id}/invoice/` | Upload JPG/PNG/PDF |
| POST | `/api/v1/web/inventory/stock-issues/` | Kitchen usage |
| POST | `/api/v1/web/inventory/wastages/` | Wastage |
| POST | `/api/v1/web/inventory/adjustments/` | Stock adjustment |
| GET | `/api/v1/web/inventory/usage-history/` | Usage list |
| GET | `/api/v1/web/inventory/reports/{report_key}/` | Allowlisted reports |
| GET | `/api/v1/web/inventory/audit-logs/` | Audit trail |

## Error codes

Envelope: `{ "success": false, "message": "...", "errors": {}, "error_code": "..." }`

| Code | HTTP | Meaning |
|------|------|---------|
| `INSUFFICIENT_STOCK` | 422 | Issue/wastage/adjustment would go negative |
| `INSUFFICIENT_WALLET_BALANCE` | 422 | Confirm blocked by Admin Wallet float |
| `DUPLICATE_ITEM_NAME` | 422 | Case-insensitive name clash |
| `UNIT_LOCKED` | 422 | `default_unit` change after stock movements |
| `INVALID_STATUS` | 422 | Item status not in allowlist |
| `INVALID_MINIMUM_STOCK` | 422 | Negative or invalid minimum |
| `INVALID_QUANTITY` / `INVALID_AMOUNT` | 422 | Bad quantity/money values |
| `UNSUPPORTED_UNIT` / `INCOMPATIBLE_UNIT` / `INVALID_UNIT` | 422 | Unit allowlist / conversion failure |
| `NAME_REQUIRED` / `ITEM_REQUIRED` / `LINES_REQUIRED` / `REASON_REQUIRED` | 422 | Required domain fields |
| `PURCHASE_CANCELLED` / `INVALID_PURCHASE_STATUS` | 422 | Purchase state machine conflict |
| `CANCEL_BLOCKED_STOCK_CONSUMED` | 422 | Cancel after stock already used |
| `ADMIN_WALLET_ERROR` | 422 | Wrapped Admin Wallet business failure |
| `UNSUPPORTED_FILTER` / `UNSUPPORTED_REPORT` | 400 | Bad query/report key |
| `INVOICE_REQUIRED` / `INVALID_INVOICE_TYPE` / `INVOICE_TOO_LARGE` | 400 | Invoice upload validation |
| `NOT_FOUND` / `ITEM_NOT_FOUND` | 404 | Missing resource |

## Local schema repair

If Admin Inventory APIs return `OperationalError: no such column` (e.g. missing `name_normalized` / `status`) while `migrate` says nothing is pending, the inventory migration was likely fake-applied over a legacy schema.

Recommended recovery (local/dev; empty inventory tables):

1. Optional: copy `db.sqlite3` as a backup.
2. Run `python manage.py repair_inventory_schema` (aborts if inventory tables have rows unless `--force`).
3. Re-test: `GET /api/v1/web/inventory/dashboard/`, create/list items, then `python manage.py test inventory.tests.test_inventory`.

Dry-run: `python manage.py repair_inventory_schema --dry-run`.

## How to verify

```bash
python manage.py migrate
python manage.py repair_inventory_schema   # only if schema mismatch
python manage.py test inventory.tests.test_inventory
python manage.py reconcile_inventory_stock
```

OpenAPI tag: **Web Inventory**.

## OpenSpec

`openspec/changes/food-inventory-system/`  
`openspec/changes/fix-inventory-schema-runtime-errors/`