## Why

Admin currently has no dedicated Customer Management surface: there is no `/api/v1/web/customers/` namespace, and staff cannot list customers, open a full profile, or inspect order / meal / wallet / meal-off history in one place. Without that, support and operations cannot verify accounts, track active packages, or analyze customer behavior. Verified Admin (`IsVerifiedAdmin` / `AdminProfile.is_verified`) already gates other web management APIs; this change adds the same-class customer management APIs and frontend docs so the Admin Panel can ship a complete Customer section.

## What Changes

- Add **Admin Customer List & Detail APIs** under `/api/v1/web/customers/` for verified admins: paginated list with search/filters and a rich detail/overview payload (basic profile, addresses, account/verification status, package and wallet summary metrics)
- Add **Customer historical resource APIs**: order history, meal (delivery) history, wallet transaction history, and meal-off history, each paginated and scoped to a single customer
- Add an **Active Orders view** (list or filter) so Admin can see customers with currently active packages: package name, start/end dates, remaining meals, status
- Surface **Meal Off Tracking** (who, which date/period, reason/note when present, counts) for Admin support and kitchen-adjacent ops
- Compute/expose **Customer summary metrics** for list and overview: total orders, meals received/off, spending, wallet balance, current package, last order/activity, registration date, account status
- Add **Frontend implementation documentation** describing Customer List, Details (tabs: Overview, Active Order, Order History, Meal History, Wallet History, Activity History), search/filters, pagination, and loading/empty/error states consistent with the existing Admin Panel
- Map customer “verification status” to existing `CustomerProfile.is_email_verified` (no new `is_verified` on customer unless product later requires it); Admin access remains `IsVerifiedAdmin`
- No **BREAKING** changes to customer-facing auth, profile, order, meal-off, or wallet APIs; this is additive admin tooling that reads existing domain data

## Capabilities

### New Capabilities

- `admin-customer-directory`: Verified-admin list/detail of customers with search, filters (active/inactive, active-order / no-active-order, package, registration date range), basic info, and overview summary metrics
- `admin-customer-history`: Paginated order, meal/delivery, wallet, and meal-off history for a single customer, plus active-order visibility for Admin
- `admin-customer-frontend-docs`: Frontend developer documentation for Admin Customer Management pages, tabs, UI states, and API integration

### Modified Capabilities

- (none) — existing customer profile, order, meal-off, and wallet contracts remain the source of truth; this change consumes them without changing customer-facing requirements

## Impact

- **Apps**: primarily `user_management` (CustomerProfile, addresses, delivery preferences; empty `web_urls.py` to be filled), `orders` (Order, OrderDelivery, meal-off), `wallet` (Wallet, WalletTransaction); possibly thin aggregation services under `user_management/services/` or shared read services
- **APIs** (web/admin only; paths finalized in design):
  - `GET /api/v1/web/customers/` — list + search/filter
  - `GET /api/v1/web/customers/{id}/` — detail/overview
  - Nested or sibling history endpoints for orders, meals, wallet, meal-off
  - Active-order listing or list filter
- **Data**: mostly read aggregates over existing models; profile picture may be absent today (document gap / optional future field)
- **Permissions**: `IsVerifiedAdmin` only; customers must not access these endpoints
- **Docs/tests**: `user_management/docs/backend/` + `user_management/docs/frontend/` (or equivalent app docs); API tests for auth, filters, pagination, object scope, and response shape
