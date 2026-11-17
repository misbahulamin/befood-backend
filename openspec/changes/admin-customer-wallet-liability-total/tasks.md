# Tasks

## 1. Backend aggregate + API contract

- [x] 1.1 Add a helper in `admin_wallet/services/queries.py` that returns `SUM(Wallet.balance)` (default `0.00`) across all customer wallets, including frozen, and verify a unit-level assertion against seeded wallets
- [x] 1.2 Include `total_customer_wallet_balance` in `wallet_summary()` and top-level `dashboard_payload()` without changing existing funding/net fields, and verify both payloads expose the same value
- [x] 1.3 Extend `AdminWalletSummarySerializer` and `AdminWalletDashboardSerializer` (plus OpenAPI helpers if present) with the new decimal field and help text contrasting `net_customer_funding`, and verify schema/serializer field presence
- [x] 1.4 Add/extend `admin_wallet` API tests: admin sees correct sum; empty wallets → `0.00`; after meal spend liability drops while `net_customer_funding` does not; customer gets `401`/`403`; verify with targeted `manage.py test` for the touched test module

## 2. Backend documentation

- [x] 2.1 Update `admin_wallet/docs/frontend/admin-wallet.md` with field name, summary-card mapping for `/admin/wallet`, meaning (sum of customer balances), and explicit warning not to use `net_customer_funding` for unconsumed prepaid; verify the doc names the dashboard/summary field and contrast
- [x] 2.2 Add a short backend note (e.g. in `admin_wallet/docs/backend/admin-wallet.md`) describing the aggregate source (`Wallet.balance`) and verify it matches the implemented helper

## 3. Frontend Admin Wallet page (befood-frontend)

- [x] 3.1 Extend `adminWalletTypes.ts` with `total_customer_wallet_balance` on summary and dashboard types and verify TypeScript compiles for Admin Wallet modules
- [x] 3.2 Add an overview `AdminStatCard` on `AdminWalletPage` bound to the new field (label for prepaid / customer wallet balances) and update help copy so it is distinct from Net customer funding; verify `/admin/wallet` shows the card from the live dashboard response
- [x] 3.3 Smoke-check overview refresh after wallet mutations/recharges in local admin UI and verify the card value tracks the sum of customer balances rather than `net_customer_funding`

## Workflow follow-up

- Archive the change after backend + frontend review requirements are satisfied.
- Sync delta specs to main specs if archiving does not already do so per project practice.
