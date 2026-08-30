# Frontend: Admin Customer Management

## Summary

Build the Admin Panel **Customer** section against `/api/v1/web/customers/`. All endpoints require a **verified admin** token. Customer verification in the UI means **email verified** (`verification_status`), not admin `is_verified`.

**Target client:** Admin web SPA only.

## Auth

```http
Authorization: Token <admin-token>
```

Non-admin users must not call these APIs. On `401`/`403`, show the standard admin session/permission error.

## Pages

### 1. Customer List

**API:** `GET /api/v1/web/customers/`

**Table columns**

| UI | API field |
|----|-----------|
| Avatar | `profile_picture_url` (nullable media/S3 URL; use placeholder when null) |
| Name | `name` |
| Email | `email` |
| Phone | `phone` |
| Account | `account_status` (`active` / `inactive`) or `is_active` |
| Verification | `verification_status` (`verified` / `unverified`) |
| Package | `current_package.package_name` (or “—” if null) |
| Registered | `registered_at` |

**Actions:** View Details → navigate to `/customers/{public_id}` (or your route).

**Search:** bind search box to `q` (name / email / phone).

**Filters**

| UI control | Query param |
|------------|-------------|
| Active / Inactive | `is_active=true\|false` |
| Verified / Unverified | `is_email_verified=true\|false` |
| Has active order | `has_active_order=true\|false` |
| Package | `meal_public_id=<package uuid>` |
| Registration range | `registered_from`, `registered_to` (`YYYY-MM-DD`) |

**Pagination:** use `count`, `next`, `previous`, `results`. Support `page` and `page_size` (max 100).

**UI states**

- Loading: table skeleton
- Empty: “No customers match your filters”
- Error: toast / inline error from `400`/`401`/`403`/`5xx`

### 2. Customer Details

Load overview first, then fetch tab data when the tab is selected (or prefetch Active Order with overview).

Base path: `/api/v1/web/customers/{public_id}/`

#### Tab 1 — Overview

**API:** `GET /api/v1/web/customers/{public_id}/`

Show:

- Basic: name, email, phone, addresses, occupation, allergies, etc.
- Account + verification badges
- Summary cards: `summary.total_orders`, `total_meals_delivered`, `total_meal_offs`, `total_wallet_spent`, `wallet_balance`, `last_order_at`, `last_activity_at`
- Optional inline current package from `active_order` / `current_package`

#### Tab 2 — Active Order

**API:** `GET .../active-order/`

- If `active_order` is null → empty state: “No active package”
- Else show package name, start/end, remaining meals, status

#### Tab 3 — Order History

**API:** `GET .../orders/`

Columns: package name, month, status, start/end, remaining/delivered/skipped counts, created date. Paginate.

#### Tab 4 — Meal History

**API:** `GET .../meals/`

Optional filters: `status`, `meal_period`, date range. Show delivered / skipped / scheduled / missed. Paginate.

For meal-off–only view you may call `GET .../meal-offs/` instead (or filter meals with `status=skipped`).

#### Tab 5 — Wallet History

**API:** `GET .../wallet-transactions/`

Columns: type, direction, amount, balance_after, status, method, note, created_at. Empty list is normal when no wallet exists (`200`, `count=0`).

#### Tab 6 — Activity History

**API:** `GET .../activity/`

Timeline of `event_type` + `summary` + `occurred_at`. Not a full audit log—compose from orders, meal-offs, and wallet events.

## Suggested call order

1. List page → `GET /customers/`
2. Open row → `GET /customers/{public_id}/` (Overview)
3. Tab clicks → corresponding nested GET (cache per tab if desired)

## UX notes

- Match existing Admin Panel table/card patterns
- Keep list lean; put heavy metrics on Overview
- Avatar placeholder when `profile_picture_url` is null
- Treat unknown future enum values defensively on status badges

## OpenSpec / backend

- Backend doc: `user_management/docs/backend/admin-customer-management.md`
- Change: `openspec/changes/admin-customer-management/`
