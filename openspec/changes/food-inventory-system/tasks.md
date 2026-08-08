## 1. App scaffold and Admin Wallet extension

- [ ] 1.1 Create `inventory` Django app package (`models`, `services`, `api`, `admin`, `management`, `tests`, `docs`) and register it in `INSTALLED_APPS`
- [ ] 1.2 Extend `AdminWalletTransaction.Type` with `inventory_purchase`, add it to debit/expense allowlists, and support inventory purchase reference/metadata on wallet transactions
- [ ] 1.3 Add `debit_for_inventory_purchase` (or equivalent) service path with idempotency key `inventory-purchase:{purchase.public_id}` and audit logging
- [ ] 1.4 Generate and apply Admin Wallet migration for the new type/reference fields

## 2. Inventory models

- [ ] 2.1 Implement `InventoryItem` (public_id, unique name, default unit, category, status, minimum_stock_level, quantity_on_hand, average_unit_cost, optional linked ingredient, created_by, timestamps)
- [ ] 2.2 Implement `InventoryPurchase` + `InventoryPurchaseLine` (status, totals, supplier, note, invoice file, actor, wallet_transaction link, line qty/unit/amounts)
- [ ] 2.3 Implement append-only `InventoryStockMovement` (type, signed delta, qty before/after, unit, actor, links to purchase/usage/wastage/adjustment, timestamps)
- [ ] 2.4 Implement kitchen usage, wastage, and adjustment header models (or equivalent typed records) with purpose/refs/notes
- [ ] 2.5 Implement `InventoryAuditLog` (actor, action, previous/new values, references, metadata, timestamps)
- [ ] 2.6 Generate and apply inventory migrations; register models in Django admin as needed

## 3. Ledger and domain services

- [ ] 3.1 Implement unit conversion helpers (`g`↔`kg`, `ml`↔`l`) and reject incompatible units
- [ ] 3.2 Implement stock movement primitive with `select_for_update`, negative-stock guard (`INSUFFICIENT_STOCK`), quantity_after, and denormalized on-hand update
- [ ] 3.3 Implement WAC update on purchase receipt and inventory valuation helper
- [ ] 3.4 Implement item master create/update services (case-insensitive unique name, low/out-of-stock signal helpers)
- [ ] 3.5 Implement purchase create, invoice attach, confirm (atomic stock + wallet debit), and cancel/reversal with cancel-rule checks
- [ ] 3.6 Implement kitchen usage, wastage, and adjustment services with audit writes
- [ ] 3.7 Implement query helpers for dashboard aggregates, purchase/usage histories, item movements, reports allowlist, and ledger reconcile check
- [ ] 3.8 Add management command to reconcile on-hand vs sum(movements) and report drift

## 4. Web Admin APIs

- [ ] 4.1 Add serializers for items, purchases/lines, confirm/cancel, stock issue/wastage/adjustment, dashboard, histories, reports, audit logs, and invoice upload
- [ ] 4.2 Implement verified-admin views for item CRUD, item movements, purchases, confirm/cancel, stock operations, histories, dashboard, reports, and audit logs
- [ ] 4.3 Mount routes under `/api/v1/web/inventory/` with `IsVerifiedAdmin` (optional permission codenames if wired)
- [ ] 4.4 Implement allowlisted filters/search/pagination; reject unsupported filters with `400`
- [ ] 4.5 Add OpenAPI/schema helpers for all new endpoints (operationIds, examples, error responses including insufficient stock/wallet)

## 5. Tests

- [ ] 5.1 Service tests: additive purchase stock, WAC calculation, unit conversion, negative-stock rejection
- [ ] 5.2 Service tests: atomic purchase confirm with wallet debit; insufficient wallet rolls back; idempotent confirm; cancel rules
- [ ] 5.3 Service tests: kitchen usage, wastage, adjustment, audit log creation, ledger reconciliation
- [ ] 5.4 API permission tests: verified admin allowed; customer/unauthenticated denied
- [ ] 5.5 API tests: dashboard, filters, purchase history, usage history, reports allowlist, invoice upload validation

## 6. Documentation and verification

- [ ] 6.1 Write `inventory/docs/backend/admin-inventory.md` (models, ledger rules, wallet atomicity, permissions, verify steps)
- [ ] 6.2 Write `inventory/docs/frontend/admin-inventory.md` (endpoint grid, field meanings, dashboard cards, purchase/usage flows, filters, wallet cross-links, error handling)
- [ ] 6.3 Update Admin Wallet frontend/backend docs with `inventory_purchase` type and cross-link to inventory purchases
- [ ] 6.4 Run relevant test suite and fix failures; smoke-check inventory endpoints in OpenAPI/Swagger if available
