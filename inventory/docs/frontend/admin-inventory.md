# Food Inventory — Frontend Integration

## Summary

Admin Panel **Inventory** section: item master, purchase → wallet debit, kitchen usage, wastage/adjustment, dashboard (low/out of stock), histories, and reports. Web-only; verified admin token required.

**Base URL:** `/api/v1/web/inventory/`  
**Auth header:** `Authorization: Token <token>`  
**Client:** web admin

Related wallet docs: `admin_wallet/docs/frontend/admin-wallet.md`  
Purchase confirm creates wallet txn type `inventory_purchase` with metadata `inventory_purchase_public_id`.

## Recommended call order

### First load (dashboard)

1. `GET /dashboard/` — paint summary cards + low/out-of-stock lists
2. Optional: `GET /items/?low_stock=true` / `GET /items/?out_of_stock=true`

### Purchase bazaar trip

1. `GET /items/` — dropdown of existing items (create missing via `POST /items/` first)
2. `POST /purchases/` with lines + optional `invoice` + `confirm: false` (draft) **or** `confirm: true`
3. If draft: `POST /purchases/{public_id}/invoice/` then `POST /purchases/{public_id}/confirm/`
4. On success: show `wallet_transaction_public_id`; refresh dashboard + Admin Wallet balance
5. On `422` + `INSUFFICIENT_WALLET_BALANCE`: block confirm UI and prompt wallet deposit

### Kitchen issue

1. `GET /items/{public_id}/` — show available stock
2. `POST /stock-issues/` with quantity/purpose
3. On `422` + `INSUFFICIENT_STOCK`: show message (includes available qty)

### Histories / finance

1. `GET /purchase-history/?date_from=&date_to=&item=&supplier=`
2. From a purchase row → open Admin Wallet txn: `GET /api/v1/web/admin-wallet/transactions/{wallet_transaction_public_id}/`
3. `GET /usage-history/`, `GET /audit-logs/`, `GET /reports/{report_key}/`

## Endpoint grid

| UI action | Method | Path |
|-----------|--------|------|
| Dashboard cards | GET | `/api/v1/web/inventory/dashboard/` |
| Item list / create | GET/POST | `/api/v1/web/inventory/items/` |
| Item detail | GET/PATCH | `/api/v1/web/inventory/items/{public_id}/` |
| Item movements | GET | `/api/v1/web/inventory/items/{public_id}/movements/` |
| Create purchase | POST | `/api/v1/web/inventory/purchases/` |
| Purchase history | GET | `/api/v1/web/inventory/purchase-history/` |
| Purchase detail | GET | `/api/v1/web/inventory/purchases/{public_id}/` |
| Confirm purchase | POST | `/api/v1/web/inventory/purchases/{public_id}/confirm/` |
| Cancel purchase | POST | `/api/v1/web/inventory/purchases/{public_id}/cancel/` |
| Upload invoice | POST | `/api/v1/web/inventory/purchases/{public_id}/invoice/` (multipart) |
| Kitchen usage | POST | `/api/v1/web/inventory/stock-issues/` |
| Wastage | POST | `/api/v1/web/inventory/wastages/` |
| Adjustment | POST | `/api/v1/web/inventory/adjustments/` |
| Usage history | GET | `/api/v1/web/inventory/usage-history/` |
| Report | GET | `/api/v1/web/inventory/reports/{report_key}/` |
| Audit | GET | `/api/v1/web/inventory/audit-logs/` |

## Dashboard cards → fields

| Card | Field |
|------|--------|
| Total items | `total_inventory_items` |
| Total stock value | `total_stock_value` |
| Today’s purchases | `today_purchases_count` / `today_purchases_amount` |
| This month purchase cost | `month_purchase_cost` |
| Low stock | `low_stock_count` + `low_stock_items[]` |
| Out of stock | `out_of_stock_count` + `out_of_stock_items[]` |
| Today’s kitchen usage | `today_kitchen_usage_count` / `today_kitchen_usage_quantity` |
| Total wastage | `total_wastage_quantity` |

## Create item

```json
POST /api/v1/web/inventory/items/
{
  "name": "Beef",
  "default_unit": "kg",
  "category": "meat",
  "minimum_stock_level": "10",
  "status": "active"
}
```

Response includes `quantity_on_hand`, `average_unit_cost`, `stock_value`, `low_stock`, `out_of_stock`.

## Create + confirm purchase

```json
POST /api/v1/web/inventory/purchases/
{
  "confirm": true,
  "supplier": "Karwan Bazar",
  "note": "Weekly meat",
  "lines": [
    {
      "item_public_id": "<uuid>",
      "quantity": "50",
      "unit": "kg",
      "line_total": "25000.00"
    }
  ]
}
```

Important response fields:

| Field | Meaning |
|-------|---------|
| `public_id` | Purchase id |
| `status` | `draft` / `confirmed` / `cancelled` |
| `total_amount` | Sum of line totals (BDT) |
| `wallet_transaction_public_id` | Link to Admin Wallet debit |
| `has_invoice` / `invoice_url` | Receipt availability |
| `lines[].unit_cost` | Cost per item default unit |

### Invoice upload

`multipart/form-data` field name: `invoice`  
Allowed: JPG, PNG, PDF (max 10MB). Confirm allowed without invoice.

## Kitchen usage

```json
POST /api/v1/web/inventory/stock-issues/
{
  "item_public_id": "<uuid>",
  "quantity": "12",
  "unit": "kg",
  "purpose": "Dinner cooking",
  "menu_reference": "2026-08-08 dinner",
  "kitchen_batch": "B-12"
}
```

Error example:

```json
{
  "success": false,
  "message": "পর্যাপ্ত stock নেই। Available Stock: 10 kg",
  "errors": {},
  "error_code": "INSUFFICIENT_STOCK"
}
```

## Wallet insufficient

```json
{
  "success": false,
  "message": "Admin Wallet-এ পর্যাপ্ত balance নেই।",
  "errors": {},
  "error_code": "INSUFFICIENT_WALLET_BALANCE"
}
```

## Error codes (operator UI)

Always prefer `error_code` + `message` from the response body (do not key UX only on HTTP status).

| Code | HTTP | UI handling |
|------|------|-------------|
| `INSUFFICIENT_STOCK` | 422 | Show `message` (includes available qty); block issue/wastage |
| `INSUFFICIENT_WALLET_BALANCE` | 422 | Block confirm; prompt Admin Wallet deposit |
| `DUPLICATE_ITEM_NAME` | 422 | Highlight item name field; ask for a different name |
| `UNIT_LOCKED` | 422 | Disable/explain that `default_unit` cannot change after stock activity |
| `INVALID_STATUS` | 422 | Reset status to `active` / `inactive` |
| `INVALID_MINIMUM_STOCK` | 422 | Highlight minimum stock field |
| `UNSUPPORTED_UNIT` / `INCOMPATIBLE_UNIT` / `INVALID_UNIT` / `INVALID_QUANTITY` | 422 | Fix unit/qty against item default unit |
| `PURCHASE_CANCELLED` / `INVALID_PURCHASE_STATUS` | 422 | Refresh purchase detail; hide stale actions |
| `CANCEL_BLOCKED_STOCK_CONSUMED` | 422 | Explain stock already used; cancel not allowed |
| `UNSUPPORTED_FILTER` / `UNSUPPORTED_REPORT` | 400 | Fix query / report key (dev-facing) |
| `INVOICE_*` | 400 | Fix file type/size (JPG/PNG/PDF, max 10MB) |

## Filters (allowlisted)

**Purchases:** `date_from`, `date_to`, `item` (item public_id), `admin` (id or email), `category`, `amount_min`, `amount_max`, `supplier`, `status`, `q`  
**Usage:** `date_from`, `date_to`, `item`, `admin`, `q`  
**Items:** `status`, `category`, `q`, `low_stock`, `out_of_stock`  
Unsupported filters → `400` / `UNSUPPORTED_FILTER`.

## Reports

`report_key` allowlist: `daily_purchase`, `weekly_purchase`, `monthly_purchase`, `item_wise_purchase`, `inventory_usage`, `wastage`, `stock_valuation`, `admin_activity`, `supplier_wise_purchase`, `expense`.

## Item detail history UI

`GET /items/{public_id}/` → `history_summary` (purchased/used/adjusted/current/value).  
`GET /items/{public_id}/movements/` → rows like `quantity_delta` + `type` + `actor_email` for timeline (`+50 | purchase | admin@…`).

## Movement types

`purchase`, `kitchen_usage`, `wastage`, `adjustment`, `purchase_reversal`
