## Why

Admin Panel `/admin/wallet` already shows cash custody metrics (`month_revenue`, funding, withdrawals) but not **realized meal profit**. Operators need lifetime and this-month profit totals, plus a package-level breakdown when they open those cards, using the same per-package / per-slot profit already locked at menu publish (`profit_percent` → `MonthlyMenuSlot.profit_snapshot`).

## What Changes

- Extend `GET /api/v1/web/admin-wallet/dashboard/` with additive profit summary fields: `total_profit`, `month_profit`, and a package-wise breakdown suitable for drill-down UI (no **BREAKING** removals of existing cash fields).
- Compute realized profit from **charged meal deliveries** joined to published slot `profit_snapshot` (and related cost/revenue snapshots where useful), grouped by meal package (`MealCategory`).
- Keep cash metrics (`today_income`, `month_revenue`, funding/withdrawals) semantically separate from meal profit so funding recharges are never counted as profit.
- Update Admin Wallet OpenAPI/serializer docs and frontend integration docs so Admin Panel can render two profit cards and a package breakdown modal/drawer from the same dashboard response (or a clearly documented companion query if pagination is required later).
- Add/extend backend tests covering profit totals and package aggregation; document recognition rules (which deliveries count, month boundary, missing-snapshot handling).

## Capabilities

### New Capabilities
- `admin-wallet-meal-profit-reporting`: Realized meal profit aggregation (lifetime + calendar month) and package-level breakdown for Admin Wallet dashboard reporting.

### Modified Capabilities
- `admin-wallet-admin-api`: Dashboard contract gains profit summary and package breakdown fields while retaining existing cash/custody cards.
- `admin-wallet-frontend-docs`: Frontend docs describe profit cards, click → package breakdown UX, field meanings, and recommended call order for `/admin/wallet`.
- `admin-wallet-meal-revenue-recognition`: Clarify that meal **revenue** (charged amounts) and meal **profit** (published slot profit snapshots) are distinct reportable metrics; profit MUST NOT be inferred from Admin Wallet cash credits.

## Impact

- **Backend:** `admin_wallet/services/queries.py`, `admin_wallet/api/serializers.py`, `admin_wallet/api/views.py` (OpenAPI), tests under `admin_wallet/tests/`; reuse delivery→meal and slot resolution from orders/meals services (read-only join to `OrderDelivery`, `MealCategory`, `MonthlyMenuSlot`).
- **API contract:** Additive fields on existing dashboard endpoint preferred so one response powers the page (matches current “single dashboard call” frontend pattern).
- **Frontend (out of this repo, planned via docs):** Admin Wallet page cards for Total Profit / This Month Profit; click opens package breakdown (package name, deliveries count, revenue, profit).
- **Data model:** No required `AdminWallet` schema change for v1 (derived aggregates). Optional later denormalization of profit onto `OrderDelivery` is out of scope unless performance forces it.
- **Dependencies:** Relies on existing publish-time slot snapshots (`meal-slot-final-price` / cycle costing); deliveries without resolvable published `profit_snapshot` contribute `0` profit and MUST be counted/documented as excluded or zeroed consistently.
