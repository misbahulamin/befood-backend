## Why

BeFood cooks every day and buys ingredients regularly, but there is no ledger-based kitchen inventory: purchases, stock increases, kitchen consumption, wastage, cost valuation, and Admin Wallet expense are not tracked in one auditable system. Without that, admins cannot reliably answer what is on hand, what was spent, who moved stock, or whether platform cash and inventory stayed consistent.

## What Changes

- Introduce a dedicated **Food Inventory** bounded context (new Django app) with an **Item Master** for kitchen ingredients/stockable items (name, default unit, category, status, minimum stock, created-by).
- Add **ledger-based stock movements** (purchase, kitchen usage, wastage, adjustment) so current quantity is reconcilable from history; never overwrite balances in place.
- Support **purchase entries** with quantity, unit, total amount, unit cost, optional supplier/note, invoice/receipt upload (JPG/PNG/PDF), acting admin, and automatic **stock increase** (additive, never overwrite).
- Support **kitchen usage / issue**, **wastage**, and **stock adjustment** with negative-stock rejection and clear available-quantity errors.
- Integrate confirmed purchases with the **BeFood Admin Wallet**: atomic wallet debit + stock ledger write; reject when wallet balance is insufficient; keep bidirectional references for financial reconciliation.
- Track **weighted average cost (WAC)** per item for inventory valuation and dashboard stock value.
- Expose **web Admin APIs** for item CRUD, purchases, usage/wastage/adjustments, item detail history, purchase/usage histories, dashboard summaries (including low/out-of-stock), allowlisted reports, and audit logs.
- Ship **backend + frontend docs** for the Admin Panel Inventory section.
- Extend Admin Wallet debit taxonomy with an **`inventory_purchase`** (or equivalent allowlisted) type and source/reference links to inventory purchases (implementation change on `admin_wallet`; no main-spec delta yet because Admin Wallet specs are not archived to `openspec/specs/`).

## Capabilities

### New Capabilities
- `inventory-item-master`: Stockable item catalog (units, category, status, min stock, low/out-of-stock signals) separate from meal costing `Ingredient`.
- `inventory-stock-ledger`: Append-only quantity ledger, denormalized on-hand + WAC fields, valuation, and balance guards (no negative stock).
- `inventory-purchasing`: Purchase workflow, invoice upload, additive stock receipt, atomic Admin Wallet debit, purchase history filters, wallet↔purchase cross-links.
- `inventory-stock-operations`: Kitchen usage/issue, wastage, and adjustment entries with actor, purpose/refs, and stock history.
- `inventory-admin-api`: Verified-admin web APIs for dashboard, item detail, histories, reports, permissions, and inventory audit log exposure.
- `inventory-frontend-docs`: Frontend contract for Admin Panel Inventory UI (dashboard cards, item master, purchase/usage flows, filters, invoice handling).

### Modified Capabilities
- _(none in `openspec/specs/`)_ — meal `ingredient-catalog` / `kitchen-cooking-requirement` remain costing/requirement APIs and are not stock ledgers. Admin Wallet behavior is extended in code + this change’s purchasing specs; archive/sync Admin Wallet main specs separately if desired.

## Impact

- **New app** (e.g. `inventory/`): models, services, web APIs under `/api/v1/web/inventory/`, admin, tests, `docs/backend` + `docs/frontend`.
- **Admin Wallet**: new debit type for inventory purchases; `post_expense` / dedicated service path; optional FK or public-id reference fields between wallet txn ↔ purchase; same `atomic()` boundary as stock receipt.
- **Media/storage**: invoice file validation (type/size) via existing media patterns.
- **Auth**: `IsVerifiedAdmin` (and optional group permission codenames) consistent with Admin Wallet / Onahar admin APIs.
- **Dependencies**: Decimal money and quantity (no floats), `PublicIdMixin`, `select_for_update` ledger style from `admin_wallet` / customer `wallet`.
- **Non-goals for this change**: replacing meal costing `Ingredient` catalog; automatic stock deduction from kitchen cooking-requirement API; multi-warehouse / multi-branch inventory; barcode/QR scanning; supplier master CRM beyond optional free-text/vendor fields; editing completed monetary purchase amounts after wallet debit without a compensating cancel/reversal flow (define cancel policy in design); mobile-only inventory routes.
