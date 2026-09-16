## 1. Profit aggregation services

- [x] 1.1 Add `meal_profit_recognized(start=None, end=None)` in `admin_wallet/services` that sums published slot `profit_snapshot` for charged deliveries (null/missing snapshot → `0.00`), filtering by `updated_at` like `meal_revenue_recognized`
- [x] 1.2 Add `meal_profit_by_package(start=None, end=None)` returning rows with `package_public_id`, `package_name`, `charged_deliveries`, `revenue`, `profit`, ordered by profit desc then name
- [x] 1.3 Reuse `delivery_meal` / `resolve_published_slot_for_delivery` (or equivalent joins) so package and slot resolution match charging rules; do not recompute from live catalog prices

## 2. Dashboard API contract

- [x] 2.1 Extend `dashboard_payload()` with `total_profit`, `month_profit`, and `profit_by_package` `{ lifetime, month }` using existing period bound helpers
- [x] 2.2 Extend `AdminWalletDashboardSerializer` (and nested package row serializer) with the new fields as decimal/string money consistent with other dashboard amounts
- [x] 2.3 Update OpenAPI/schema descriptions on the dashboard view so profit fields are documented as meal margin (not cash `month_revenue`)

## 3. Tests

- [x] 3.1 Test lifetime and month profit totals from charged deliveries with known slot `profit_snapshot` values
- [x] 3.2 Test package breakdown groups correctly and month/lifetime lists match top-level profit sums
- [x] 3.3 Test funding credits do not inflate profit; missing snapshot contributes zero without failing the dashboard
- [x] 3.4 Test verified-admin success and non-admin denial still hold for the extended dashboard response

## 4. Documentation (backend + frontend plan)

- [x] 4.1 Update `admin_wallet/docs/backend/admin-wallet.md` with profit recognition rules (`updated_at` window, snapshot source, cash vs profit distinction)
- [x] 4.2 Update `admin_wallet/docs/frontend/admin-wallet.md` with Total Profit / This Month Profit card mapping, click → `profit_by_package.lifetime|month` breakdown columns, and warning not to use `month_revenue` as profit
- [x] 4.3 Include example dashboard JSON snippet showing the new fields for Admin Panel integration

## 5. Verification

- [x] 5.1 Run focused admin_wallet (and related) tests for dashboard/profit coverage
- [x] 5.2 Manually smoke `GET /api/v1/web/admin-wallet/dashboard/` as verified admin and confirm profit cards data shape matches the frontend doc
