## Why

The Admin Customer Detail page (`/admin/customers/:publicId`) exists in `befood-frontend` and is wired to `/api/v1/web/customers/`, but it still models the customer lifecycle around legacy **Order** concepts (`Active order`, `Order history`). Befood's current business model treats **CustomerSubscription** as the customer's active service — `POST /orders/` is retired (409) and new customers subscribe via `/api/v1/subscriptions/`. As a result, subscribed customers often show an empty Active Order tab, meal history under-counts subscription-owned deliveries, and summary metrics do not reflect reality. Admins cannot answer basic support questions ("What package is this customer on?", "How many meals delivered?", "What's their wallet status?") from one page without cross-querying separate admin subscription APIs.

## What Changes

- **Subscription-first Customer 360**: Replace Order-centric admin customer APIs and UI with **Active Subscription** and **Subscription History** as the primary service record; keep legacy Order data as historical read-only context where needed
- **Overview API aggregation (lean detail, lazy history)**:
  - `GET /api/v1/web/customers/{public_id}/` returns **only** profile, `summary` metrics, `active_subscription` summary (nullable), and `wallet_summary` (nullable) — **no paginated history arrays**
  - All history remains on lazy-loaded paginated sub-resources: `/subscriptions/`, `/meals/`, `/meal-offs/`, `/wallet-transactions/`, `/activity/`
  - Explicit performance rule: overview MUST NOT embed subscription lists, meal rows, wallet transaction rows, or activity events
- **Backend API updates** under `/api/v1/web/customers/{public_id}/`:
  - Add `active-subscription` sub-resource and `active_subscription` summary on detail overview
  - Add paginated `subscriptions` sub-resource (current + past subscriptions for one customer)
  - Make meal/meal-off queries subscription-aware (`OrderDelivery` via `order__customer` OR `subscription__customer`)
  - Extend `summary` with support-oriented metrics: customer lifetime value (`total_wallet_spent` or documented CLV field), `last_payment_at`, `last_meal_delivered_at`, `current_package_expires_at` (nullable)
  - Activity feed uses **confirmed events only** (`subscription_created`, `subscription_cancelled`, `wallet_transaction_completed`, `meal_delivered`, `meal_skipped`, legacy order events) — MUST NOT infer events from `OrderDelivery.updated_at` alone
  - Add `wallet-overview` sub-resource with manual-funding-aware fields: `available_balance`, `pending_recharge_amount`, `pending_withdraw_amount`, `total_recharged`, `total_withdrawn`, `total_spent`
  - Subscription `status` values MUST come from backend model/serializer choices (not hardcoded frontend enums) to allow future values (`pending`, `expired`, `paused`, `completed`, etc.)
  - Additive list filters: `has_active_subscription`, `has_wallet`, `has_pending_recharge`, `subscription_expiring_soon`, `inactive_subscription` (keep `has_active_order` as deprecated alias)
  - **Object-level isolation**: authenticated customers MUST receive `403` when accessing another customer's admin detail or nested resources (e.g., Customer A token → `/customers/customer-B-id/` → `403`)
- **BREAKING (admin web API)**: Deprecate `/active-order/` and `/orders/` nested routes in favor of `/active-subscription/` and `/subscriptions/`; maintain backward-compatible aliases with `Deprecation` response headers for one release cycle unless product approves immediate removal
- **Frontend redesign** in `befood-frontend`: rename tabs (Active Subscription, Subscription History), add Wallet Overview tab, fix serializer field mismatches, enrich Overview with full profile fields, add header summary cards (active subscription, wallet balance, meals delivered, total subscriptions, CLV, last payment, last meal, package expiry)
- **Legacy orders UI (migration period)**: collapsible "Legacy monthly orders" section on customer detail **only when** the customer has pre-migration `Order` rows; hidden otherwise. Subscription remains primary.
- **Documentation**: Update `user_management/docs/backend/` and `user_management/docs/frontend/admin-customer-management.md` to subscription-first contracts
- **No customer-facing API changes**; verified-admin read-only scope preserved (`IsVerifiedAdmin`)

## Capabilities

### New Capabilities

- (none — this change extends existing admin customer capabilities rather than introducing a new domain)

### Modified Capabilities

- `admin-customer-directory`: Subscription-first list/detail overview — active subscription summary, subscription-aware filters/metrics, enriched profile fields on detail
- `admin-customer-history`: Replace active-order/order-history requirements with active-subscription/subscription-history; subscription-aware meal/meal-off/wallet/activity feeds; wallet overview summary
- `admin-customer-frontend-docs`: Document subscription-first tab structure (Overview, Active Subscription, Subscription History, Meal History, Meal-offs, Wallet Overview, Wallet History, Activity), field mappings, and empty-state guidance

## Impact

- **Backend (`befood-backend`)**: `user_management/services/admin_customer.py`, `user_management/api/admin_customer_views.py`, `user_management/api/admin_customer_serializers.py`, tests under `user_management/tests/`, OpenAPI, backend docs
- **Orders domain (read-only reuse)**: `orders.models.CustomerSubscription`, `orders.services.subscription_service.get_active_subscription`, `OrderDelivery` dual-parent queries
- **Wallet domain (read-only reuse)**: `wallet.models.Wallet`, `WalletTransaction` — wallet overview and txn payloads MUST surface pending manual recharge/withdraw amounts from the manual funding review flow (`manual-recharge-withdraw` change) when applicable
- **Frontend (`befood-frontend`)**: `AdminCustomerDetailPage.tsx`, `adminCustomerApi.ts`, `useAdminCustomers.ts`, `customerManagementTypes.ts`, `customerManagementDisplay.ts`
- **Out of scope**: Admin mutations (ban, edit profile), payment gateway (`PaymentIntent`), Onahar charity progress, device/login history — documented as future enhancements
- **Dependencies**: Requires subscription-based meal service already deployed (`CustomerSubscription`, `OrderDelivery.subscription` FK)
