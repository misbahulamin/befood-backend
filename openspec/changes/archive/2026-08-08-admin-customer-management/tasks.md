## 1. Customer public id and foundation

- [x] 1.1 Add `PublicIdMixin` (UUID `public_id`) to `CustomerProfile` with migration and backfill for existing rows; unique non-null constraint
- [x] 1.2 Confirm `IsVerifiedAdmin` permission reuse for all new web customer endpoints
- [x] 1.3 Mount `path('api/v1/web/customers/', include('user_management.api.web_urls'))` in `core/urls.py` and scaffold `user_management/api/web_urls.py`

## 2. Admin customer directory service and list/detail APIs

- [x] 2.1 Implement `user_management/services/admin_customer.py` helpers: base queryset with `select_related('user')`, search (`q` on name/email/phone), filters (`is_active`, `is_email_verified`, `has_active_order`, package, registration date range), current active order resolution, remaining-meal count via scheduled `OrderDelivery`
- [x] 2.2 Implement overview summary metrics (total orders, delivered meals, meal-offs, `total_wallet_spent`, wallet balance, last order/activity dates, `profile_picture_url=null`)
- [x] 2.3 Add admin list/detail serializers (lean list vs rich overview) using `public_id` and verification/account status mapping from `is_email_verified` / `User.is_active`
- [x] 2.4 Implement `GET /api/v1/web/customers/` (paginated, allowlisted filters, deterministic sort) and `GET /api/v1/web/customers/{public_id}/` with `IsVerifiedAdmin`, OpenAPI helpers
- [x] 2.5 API tests: list success fields, search, each filter, pagination, auth `401`/`403`, detail `200`/`404`, verification mapping

## 3. Active order and history APIs

- [x] 3.1 Implement `GET /api/v1/web/customers/{public_id}/active-order/` (package, start/end, remaining meals, status; documented empty when none)
- [x] 3.2 Implement paginated `GET .../orders/` order history scoped to customer
- [x] 3.3 Implement paginated `GET .../meals/` delivery history with allowlisted status/period/date filters
- [x] 3.4 Implement paginated `GET .../meal-offs/` (skipped deliveries + note/skip_source) or equivalent documented meal-history filter
- [x] 3.5 Implement paginated `GET .../wallet-transactions/` (empty list if no wallet; `404` only if customer missing)
- [x] 3.6 Implement paginated `GET .../activity/` composed from order/meal-off/wallet events
- [x] 3.7 Wire nested routes in `web_urls`, OpenAPI examples, and API tests: scoping (no cross-customer leak), empty wallet, filters `400`, auth denial

## 4. Docs and verification

- [x] 4.1 Write backend docs `user_management/docs/backend/admin-customer-management.md` (endpoint grid, permissions, field meanings, examples, errors)
- [x] 4.2 Write frontend docs `user_management/docs/frontend/admin-customer-management.md` (list page, detail tabs Overview/Active Order/Order/Meal/Wallet/Activity, search/filters, pagination, loading/empty/error, auth/verification semantics)
- [x] 4.3 Register `CustomerProfile` admin niceties if useful for ops (optional list display of `public_id` / verification); do not block SPA APIs on Django admin
- [x] 4.4 Run targeted admin-customer API tests and fix regressions
