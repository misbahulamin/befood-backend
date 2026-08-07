## Context

Befood already has rich customer domain data, but no Admin Panel customer management API:

- **Identity**: `auth.User` (name, email, `is_active`, `date_joined`) + `CustomerProfile` (phone, preferences, `is_email_verified`, profile fields) in `user_management`
- **Addresses / delivery**: `CustomerAddress`, `CustomerDeliveryPlace`, `MealDeliveryPreference`, day overrides
- **Orders**: `Order` → `CustomerProfile`; statuses `pending|confirmed|active|completed|cancelled`; package via `MealCategory`; progress via `OrderDelivery` (`scheduled|delivered|skipped|missed`)
- **Meal off**: `OrderDelivery.status=skipped` + `skip_source` + optional `note`; no separate MealOff model
- **Wallet**: `Wallet` (1:1 customer) + append-only `WalletTransaction` (`recharge|withdraw|payment|refund|adjustment`)
- **Admin auth**: `IsVerifiedAdmin` / `is_verified_admin` (`AdminProfile.is_verified` + `ADMIN` group) — same gate as deliveryman admin and web order tools
- **Gap**: `user_management/api/web_urls.py` is empty; no `/api/v1/web/customers/` mount; `CustomerProfile` has **no** `public_id` today (addresses/orders/wallet txs already use `PublicIdMixin`)

Stakeholders: Admin SPA (Customer section), support ops. Customer-facing APIs stay unchanged.

Constraints: snake_case JSON; paginate collections; money as Decimal/string; web routes under `/api/v1/web/...`; verified-admin only; reuse existing models as source of truth (read/aggregate, prefer not invent parallel status tables).

## Goals / Non-Goals

**Goals:**

- Verified-admin Customer directory: list, search, filter, detail/overview with summary metrics
- Nested historical APIs: orders, meal deliveries, wallet transactions, meal-off (skipped) slots
- Active-order visibility (list filter and/or detail tab payload)
- Stable public UUID for customer resources in admin APIs
- Backend + frontend docs under `user_management/docs/` matching existing doc patterns

**Non-Goals:**

- Customer self-service profile/order/wallet API changes
- Admin editing customer profile, force-verify, ban workflow beyond exposing `User.is_active` / `is_email_verified` (mutations deferred unless product asks)
- New profile-picture upload pipeline in v1 (field does not exist; API may return `profile_picture_url: null`)
- Dedicated Activity event store / audit log product (v1 Activity tab composes from existing order/meal-off/wallet events)
- Mobile lean customer-management variants
- Changing meal-off, wallet debit, or order lifecycle rules
- Replacing Django admin CRUD for `CustomerProfile` (optional register/list is fine; SPA APIs are primary)

## Decisions

### 1. Mount under `/api/v1/web/customers/` in `user_management`

**Choice:** Fill `user_management.api.web_urls` and mount in `core/urls.py`:

```text
path('api/v1/web/customers/', include('user_management.api.web_urls'))
```

Suggested resources:

| Purpose | Method / path |
|--------|----------------|
| List + search/filter | `GET /api/v1/web/customers/` |
| Detail / overview | `GET /api/v1/web/customers/{public_id}/` |
| Active order (current package) | `GET /api/v1/web/customers/{public_id}/active-order/` |
| Order history | `GET /api/v1/web/customers/{public_id}/orders/` |
| Meal / delivery history | `GET /api/v1/web/customers/{public_id}/meals/` |
| Meal-off history | `GET /api/v1/web/customers/{public_id}/meal-offs/` |
| Wallet history | `GET /api/v1/web/customers/{public_id}/wallet-transactions/` |
| Activity feed (composed) | `GET /api/v1/web/customers/{public_id}/activity/` |
| Global active-order customers (optional list helper) | `GET /api/v1/web/customers/?has_active_order=true` (preferred over a second collection) |

**Why:** Matches multi-client web management pattern (`/api/v1/web/orders/`) and the empty `web_urls.py` hook. Keeps customer-facing `/user_management/...` routes untouched.

**Alternatives:** Mirror deliveryman under `/user_management/admin/customers/` — rejected for Admin SPA consistency with newer web order/kitchen APIs.

### 2. Add `public_id` to `CustomerProfile`

**Choice:** Add `PublicIdMixin` (or equivalent UUID field) to `CustomerProfile` via migration; backfill existing rows; admin APIs use `lookup_field = "public_id"`. Never expose sequential profile PK in these contracts.

**Why:** Project public-UUID convention; deliveryman admin already uses `public_id`; nested history URLs need a stable opaque id.

**Alternatives:** Lookup by email/phone — rejected (PII in URLs, not opaque). Use `User.id` — rejected (sequential, auth-model leak).

### 3. Verification & account status mapping (no new `is_verified` on customer)

**Choice:** Expose:

- `verification_status`: derived from `CustomerProfile.is_email_verified` (`verified` | `unverified`) plus optional `email_verified_at`
- `account_status` / `is_active`: from `User.is_active`
- Admin Panel “Verification Status” column binds to email verification, **not** `AdminProfile.is_verified`

**Why:** Customer domain already uses email verification for login/`IsVerifiedCustomer`; inventing a second `is_verified` would duplicate state and confuse with admin/rider verification.

**Alternatives:** Add `CustomerProfile.is_verified` mirroring rider approval — deferred; customers are not in an approve-queue today.

### 4. Aggregation service layer

**Choice:** Introduce `user_management/services/admin_customer.py` (name flexible) that:

- Builds list querysets with `select_related('user')` and annotated metrics where cheap
- Resolves current package = latest/non-cancelled order with `order_status=active` (else null)
- Computes remaining meals from `OrderDelivery` with `status=scheduled` (reuse order serializer/service helpers where possible)
- Builds overview summary: total orders, delivered count, skipped (meal-off) count, wallet balance, total spending (sum of completed payment debits or order snapshots — pick one and document), last order date, last activity date
- Does **not** take `Request`; views stay thin

Cross-app reads from `orders` and `wallet` models/services are allowed; avoid duplicating meal-off deadline logic.

**Why:** Matches django-drf-conventions (services for multi-model reads/workflows).

### 5. List search & filters

**Choice:** Query params (allowlisted; reject unknown/invalid with `400`):

| Param | Behavior |
|-------|----------|
| `q` | Search name (`first_name`/`last_name`), email, phone (icontains / normalized phone) |
| `is_active` | `true`/`false` → `User.is_active` |
| `is_email_verified` | `true`/`false` |
| `has_active_order` | `true`/`false` → exists `Order` with `order_status=active` |
| `package_id` / `meal_public_id` | Customers whose **active** (or optionally any) order references that `MealCategory` |
| `registered_from` / `registered_to` | Filter on `User.date_joined` (date range, inclusive as documented) |
| `sort` | Allowlisted, default `-date_joined` with `public_id` tie-breaker |

Pagination: project standard page size + max; deterministic ordering.

**Why:** Matches product requirements without inventing free-form filter DSL.

### 6. History endpoints are read-only projections

**Choice:**

- **Orders**: serialize admin-safe order rows (status, package snapshots, dates, payment-related fields already on order/deliveries)
- **Meals**: list `OrderDelivery` for the customer’s orders (filterable by status, period, date range)
- **Meal-offs**: subset where `status=skipped` (expose `skip_source`, `note`, date, period, order/package refs)
- **Wallet**: list `WalletTransaction` for the customer’s wallet (type/direction/amount/balance_after/status/timestamps)
- **Activity**: merge recent events (order created/status changes if available, meal-off, wallet txs) into a unified timeline DTO with `event_type`, `occurred_at`, `summary`, `refs` — bounded page size

**Why:** No new history tables in v1; existing ledgers are authoritative.

### 7. Profile picture

**Choice:** Response field `profile_picture_url` always present, value `null` until a future upload feature exists. Frontend docs show avatar placeholder.

**Why:** Unblocks UI layout without a storage/migration scope creep.

### 8. Authorization

**Choice:** `IsVerifiedAdmin` on all customer web endpoints. Object scope: any customer profile is visible to verified admins (single-tenant product). Customers and deliverymen get `403`.

### 9. Docs split

**Choice:**

- `user_management/docs/backend/admin-customer-management.md` — endpoints, permissions, fields, examples
- `user_management/docs/frontend/admin-customer-management.md` — list page, detail tabs, search/filters, pagination, loading/empty/error

Frontend docs capability is fulfilled by the frontend doc artifact + OpenAPI helpers on views.

## Risks / Trade-offs

- **[Risk] Heavy list annotations (totals per customer) → slow list** → Mitigation: keep list payload lean (basic fields + current package name + wallet balance + flags); push expensive totals to detail/overview only; annotate with subqueries carefully; paginate.
- **[Risk] `public_id` migration on large `CustomerProfile` table** → Mitigation: add nullable UUID, backfill, then constrain unique/non-null in same or follow-up migration; generate defaults via mixin.
- **[Risk] Ambiguous “total spending”** → Mitigation: document as sum of completed wallet `payment` debits (meal charges) unless product prefers order `total_price_snapshot` sum; expose field name `total_wallet_spent` vs `total_order_value` if both needed.
- **[Risk] Activity feed incompleteness** → Mitigation: document composed sources; do not claim full audit completeness in v1.
- **[Trade-off] Read-only v1** → Admins cannot edit/ban from this API yet; Django admin or follow-up change for mutations.
- **[Trade-off] No profile photo** → UI placeholder until asset pipeline exists.

## Migration Plan

1. Add `public_id` to `CustomerProfile`; backfill; unique index.
2. Implement admin customer service + serializers + viewset + `web_urls` + `core/urls` mount.
3. Ship list/detail first; then nested history endpoints.
4. Add tests (authz, filters, pagination, history scoping, 404).
5. Write backend + frontend docs; OpenAPI annotations.
6. Rollback: unmount routes; keep `public_id` column (harmless).

## Open Questions

- Should Admin be able to toggle `User.is_active` or resend verification from this UI in v1? **Default: read-only; document as follow-up.**
- Exact spending metric: wallet payments vs order snapshots? **Default: expose both `total_orders` and `total_wallet_spent` (completed payment debits) on overview.**
- Include `pending`/`confirmed` orders in “current package” or only `active`? **Default: prefer `active`; if none, optionally surface latest `confirmed` as “upcoming” separately in active-order endpoint.**
- Global “Active Order Management” as its own page vs filter on customer list? **Default: same list with `has_active_order=true` plus detail Active Order tab; no separate resource collection in v1.**
