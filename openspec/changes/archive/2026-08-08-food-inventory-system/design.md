## Context

BeFood already has:

- Meal costing **`Ingredient`** catalog (`meals.Ingredient`) used for cycle costing, menus, and kitchen cooking-requirement quantities — **not** a stock ledger.
- **Admin Wallet** (`admin_wallet/`) with append-only cash ledger, `debit_admin_wallet` / `post_expense`, verified-admin web APIs, and audit logs.
- Kitchen cooking-requirement APIs that compute *needed* kg for a service slot — they do **not** decrement physical stock.

There is no purchase→stock→usage→wastage→wallet pipeline for kitchen ingredients. Product needs a secure, ledger-based Food Inventory system integrated with Admin Wallet for purchase cash-out.

Stakeholders: verified admins (ops/kitchen/finance), Admin Panel frontend, Admin Wallet ledger consumers, future kitchen automation.

Constraints:

- Business logic in `services/`; thin DRF views; Decimal money/quantity; `PublicIdMixin`; web routes under `/api/v1/web/...` with `IsVerifiedAdmin`.
- OpenAPI + tests + backend/frontend docs in the same change.
- Do not mix customer liability wallet with platform cash or inventory stock tables.
- Prefer patterns from `admin_wallet` (atomic ledger + denormalized balance + `select_for_update`).

## Goals / Non-Goals

**Goals:**

- Item Master for stockable kitchen items with default units, category, min stock, and status.
- Append-only inventory quantity ledger with reconcilable on-hand quantity and WAC valuation.
- Purchase confirm → additive stock + Admin Wallet debit in one DB transaction; invoice upload linked to purchase.
- Kitchen usage, wastage, and adjustment with hard negative-stock rejection.
- Admin activity / audit records for sensitive inventory actions.
- Dashboard summaries, filterable histories, and core reports via web APIs.
- Clear separation from meal costing `Ingredient` (optional soft link only).

**Non-Goals:**

- Replacing or merging with `meals.Ingredient` costing catalog.
- Automatic stock issue from kitchen cooking-requirement (manual issue in v1; hook can come later).
- Multi-warehouse / multi-branch stock.
- Full supplier CRM / PO approval workflow.
- Mobile-only inventory routes.
- Editing completed purchase monetary fields after wallet debit without a cancel/reversal path.
- Real-time push notifications (dashboard/list signals are enough for v1).

## Decisions

### 1. New app: `inventory/`
- **Choice:** Create `inventory/` bounded context (models, services, `api/`, admin, tests, docs). Mount under `/api/v1/web/inventory/`.
- **Rationale:** Stock + purchase + kitchen issue is a different domain than meal costing or Admin Wallet cash.
- **Alternatives considered:** Extend `meals.Ingredient` with quantity fields — conflates pricing catalog with stock and risks breaking costing APIs; put under `admin_wallet/` — wrong aggregate root.

### 2. Separate Item Master from meal `Ingredient`
- **Choice:** `InventoryItem` is the stock SKU. Optional nullable FK `linked_ingredient` → `meals.Ingredient` for future menu/requirement mapping. Names are unique (case-normalized) within inventory.
- **Rationale:** Costing ingredients exist without stock; stock items (oil, salt bags) may not be meal-line products. Dropdowns use InventoryItem, not free-text names.
- **Alternatives considered:** Force 1:1 with Ingredient — too rigid for v1 kitchen ops.

### 3. Units and conversion
- **Choice:** Allowlisted units: `kg`, `g`, `l`, `ml`, `piece`, `packet`, `box`, `bottle`, `bag`. Each item has `default_unit`. Stock is stored and ledgered in the item’s **base/default unit**. Purchase/usage requests MAY send a convertible unit only for mass/volume pairs (`g`↔`kg`, `ml`↔`l` at 1000); incompatible unit mismatch is rejected. Non-convertible units (piece/packet/…) MUST match the item default.
- **Rationale:** Product asks for consistent conversion; limiting to SI mass/volume keeps logic correct without a full UoM engine.
- **Alternatives considered:** Free-form units — breaks valuation; full UoM tables — overkill for v1.

### 4. Ledger-first stock
- **Choice:** `InventoryStockMovement` is append-only (`purchase`, `kitchen_usage`, `wastage`, `adjustment`, `purchase_reversal`). Services lock `InventoryItem` with `select_for_update`, write movement with `quantity_delta` (+/−), `quantity_after`, update denormalized `quantity_on_hand` and WAC fields in the same `atomic()` block. Current stock MUST equal opening + sum(deltas) for reconciliation checks.
- **Rationale:** Matches Admin Wallet / customer wallet auditability; product §23.
- **Alternatives considered:** Balance-only updates — fails history/debug requirements.

### 5. Purchase header + lines
- **Choice:** `InventoryPurchase` (header: date, supplier, note, invoice file, status, totals, actor, wallet txn link) with one or more `InventoryPurchaseLine` (item, quantity, unit, line total, unit cost). v1 API MAY accept single-item create that still creates header+one line (multi-line supported in model for market runs). Confirming a purchase (`draft` → `confirmed`) posts stock movements per line and debits Admin Wallet for `total_amount` once.
- **Rationale:** Real bazaar trips are multi-item; single invoice + one wallet debit; atomic commit.
- **Alternatives considered:** One DB row per purchase only — forces N wallet debits per trip or awkward invoice reuse.

### 6. Atomic wallet integration
- **Choice:** On purchase confirm, inside one `transaction.atomic()`:
  1. Lock wallet + affected items.
  2. Validate wallet balance ≥ purchase total.
  3. Post stock movements / update WAC / on-hand.
  4. Debit Admin Wallet with type `inventory_purchase`, source/reference pointing at purchase `public_id`, idempotency key `inventory-purchase:{purchase.public_id}`.
  5. Store bidirectional links (`purchase.wallet_transaction`, wallet txn metadata/FK when available).
  Any failure rolls back all. Insufficient balance → `422` with code like `INSUFFICIENT_WALLET_BALANCE`.
- **Rationale:** Product §§9–11, §26.
- **Alternatives considered:** Post-commit wallet debit — risk of stock without cash; expense-only without typed link — weak reconciliation.

### 7. Admin Wallet type extension
- **Choice:** Add `AdminWalletTransaction.Type.INVENTORY_PURCHASE = 'inventory_purchase'` to debit allowlist; prefer a dedicated `debit_for_inventory_purchase(...)` wrapper (or `post_expense` with that type) that sets source=`Inventory Purchase` and reference=`Purchase #{public_id}`.
- **Rationale:** Filterable typed expense distinct from generic `operational_expense`.
- **Alternatives considered:** Reuse `operational_expense` only — weaker reporting.

### 8. Weighted average cost (WAC)
- **Choice:** On purchase receipt of quantity `q` at unit cost `c` when on-hand is `Q` at average `A`:
  - `new_avg = (Q*A + q*c) / (Q+q)` (Decimal); if `Q+q == 0`, leave avg unchanged / null.
  - Usage/wastage reduce quantity but **do not** change WAC.
  - Positive adjustment MAY optionally accept a cost hint; default: keep WAC unchanged.
  - Inventory value = `quantity_on_hand * average_unit_cost`.
- **Rationale:** Product §§20–21; standard perpetual inventory averaging.
- **Alternatives considered:** FIFO lots — better COGS accuracy, much more complex for v1.

### 9. Negative stock forbidden
- **Choice:** Any outbound movement (`kitchen_usage`, `wastage`, negative `adjustment`) MUST reject when `quantity > quantity_on_hand` with a client-safe message including available quantity and unit (Bangla-capable detail string allowed in API message; machine `error_code` e.g. `INSUFFICIENT_STOCK`).
- **Rationale:** Product §5.

### 10. Low / out-of-stock signals
- **Choice:** Item stores `minimum_stock_level` (nullable). Derived: `out_of_stock` when on-hand `<= 0`; `low_stock` when `minimum` set and `0 < on-hand < minimum` (or `<= minimum` — **use `on-hand <= minimum` and on-hand > 0 for low, =0 for out**). Dashboard endpoints return counts + short lists. Lifecycle `status` on item remains admin `active`/`inactive`; stock signals are separate read-only flags.
- **Rationale:** Product §§17–18 without overloading active/inactive.

### 11. Invoice upload
- **Choice:** `FileField` on purchase (or related `InventoryPurchaseInvoice`) accepting `image/jpeg`, `image/png`, `application/pdf` with max size from settings (e.g. 5–10 MB). Stored via default/media storage; download/open via authenticated admin detail URL. Invoice optional at draft create; **required before confirm** OR optional entirely — **Decision: optional but strongly recommended; confirm allowed without invoice** to avoid blocking ops, with audit noting missing invoice.
- **Rationale:** Product §8; ops may photograph later.
- **Alternatives considered:** Hard-require invoice — can block legitimate entries.

### 12. Cancel / reverse purchase
- **Choice:** Confirmed purchases MAY be cancelled only if resulting stock after reversing purchase quantities would not go negative (i.e. enough unused purchased qty still on hand — conservative: require `quantity_on_hand >= purchased_qty` per line for simple v1, or track remaining). Cancel posts `purchase_reversal` stock movements and credits Admin Wallet (or posts compensating credit) with idempotency; audit logged. Draft purchases delete/discard without wallet impact.
- **Rationale:** Avoid inconsistent money/stock; product mentions purchase cancelled in audit.
- **Alternatives considered:** Immutable purchases forever — too rigid when data entry errors happen.

### 13. Kitchen usage references
- **Choice:** Optional fields: `purpose`, `note`, `menu_reference` (string), `kitchen_batch` (string), optional FKs later to meal period/date. No auto-issue from cooking requirement in v1.
- **Rationale:** Product §4 optional refs without coupling.

### 14. Authorization & audit
- **Choice:** All inventory web endpoints require `IsVerifiedAdmin`. Optional permission codenames (`inventory.view`, `inventory.purchase`, `inventory.issue`, `inventory.adjust`) if `HasGroupPermission` wiring is cheap; otherwise verified-admin + audit. `InventoryAuditLog` records action, actor, item/purchase refs, previous/new stock (and wallet amount when relevant), metadata JSON.
- **Rationale:** Product §§7, §29.

### 15. Dashboard & reports
- **Choice:** Query service computes summary cards from items + movements + purchases (timezone-aware “today” / month like Admin Wallet). Report endpoints are allowlisted report keys returning paginated/tabular JSON (CSV export optional later). Unsupported report keys → `400`.
- **Rationale:** Product §§19, §27 without building a BI stack.

### 16. API shape (web)
- Rough resource map:
  - `GET/POST /items`, `GET/PATCH /items/{public_id}`
  - `GET /items/{public_id}/movements`
  - `GET/POST /purchases`, `GET /purchases/{public_id}`, `POST /purchases/{public_id}/confirm`, `POST /purchases/{public_id}/cancel`
  - `POST /stock-issues` (kitchen usage), `POST /wastages`, `POST /adjustments`
  - `GET /purchase-history`, `GET /usage-history`
  - `GET /dashboard`, `GET /reports/{report_key}`, `GET /audit-logs`
- Pagination, allowlisted filters, problem+json / project error envelope consistency.

## Risks / Trade-offs

- **[Risk] Double-spend / partial wallet debit** → Mitigation: single `atomic()` + wallet idempotency key per purchase; no post-commit dual write.
- **[Risk] WAC drift after reversals/adjustments** → Mitigation: define reversal to restore quantity and recompute or document that cancel only allowed when full qty still on hand; add reconcile command comparing sum(movements) vs on-hand.
- **[Risk] Confusion with meal `Ingredient` names** → Mitigation: docs + optional link field; UI copy “Inventory Item” vs “Costing Ingredient”.
- **[Risk] Large invoice files** → Mitigation: content-type allowlist + size cap; virus scanning out of scope.
- **[Risk] Concurrent issues overdraw stock** → Mitigation: `select_for_update` on item row before outbound movements.
- **[Trade-off] Optional invoice on confirm** → Faster ops vs weaker audit trail; UI should warn.
- **[Trade-off] Simple cancel rule (full qty still on hand)** → Some purchases won’t cancel after partial use; use wastage/adjustment + manual wallet adjust instead.

## Migration Plan

1. Add `inventory` app + migrations; extend `admin_wallet` type enum + optional purchase reference field/migration.
2. Deploy code; no backfill required (empty stock).
3. Admins seed Item Master, then create purchases.
4. Rollback: disable routes / feature flag if needed; do not delete ledger rows; reversing wallet types must remain in enum once shipped.

## Open Questions

- Should multi-line purchase be required in the first Admin Panel UI, or single-item UX first against a multi-line-capable API?
- Exact max invoice file size and whether PDF preview is in-browser vs download-only.
- Whether purchase confirm should be explicit two-step (`draft` then `confirm`) or create-and-confirm in one POST for v1 (API can support both: `confirm=true` flag).
