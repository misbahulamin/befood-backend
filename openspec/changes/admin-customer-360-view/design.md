## Context

### Current state (Phase 1 analysis — completed)

**Repositories**

| Repo | Role |
|------|------|
| `befood-backend` | Django/DRF — admin customer APIs at `/api/v1/web/customers/` |
| `befood-frontend` | React Admin SPA — Customer list/detail pages |

**Frontend structure** (`befood-frontend`)

| Item | Location |
|------|----------|
| Customer list | `src/features/admin/pages/AdminCustomersPage.tsx` |
| Customer detail | `src/features/admin/pages/AdminCustomerDetailPage.tsx` (~740 lines, inline tab components) |
| API layer | `src/features/admin/api/adminCustomerApi.ts` |
| Hooks | `src/features/admin/hooks/useAdminCustomers.ts` |
| Types | `src/features/admin/types/customerManagementTypes.ts` |
| Display utils | `src/features/admin/utils/customerManagementDisplay.ts` |
| Routes | `/admin/customers`, `/admin/customers/:publicId` (UUID, not integer id) |

**Current tabs (frontend)**

1. Overview — loads with `GET .../{publicId}/`
2. Active order — `GET .../active-order/`
3. Order history — `GET .../orders/`
4. Meal history — `GET .../meals/`
5. Meal-offs — `GET .../meal-offs/`
6. Wallet history — `GET .../wallet-transactions/`
7. Activity — `GET .../activity/`

Tab data is lazy-loaded via React Query (`enabled: tab === '...'`).

**Backend structure** (`befood-backend`)

| Item | Location |
|------|----------|
| ViewSet | `user_management/api/admin_customer_views.py` |
| Serializers | `user_management/api/admin_customer_serializers.py` |
| Service logic | `user_management/services/admin_customer.py` |
| URL mount | `core/urls.py` → `user_management/api/web_urls.py` |
| Permission | `IsVerifiedAdmin` (read-only GET) |

**Business model mismatch (root cause)**

```
Legacy model (admin customer still uses this):
  Customer subscribes → Order (monthly, order_status=active) → OrderDelivery

Current model (customer-facing, since subscription migration):
  Customer subscribes → CustomerSubscription (status=active) → OrderDelivery
  POST /orders/ → 409 SUBSCRIBE_REQUIRED
  GET /orders/current-package/ → returns subscription payload
```

`admin_customer.py` functions still filter exclusively on `Order`:

- `get_active_order()` — `Order.objects.filter(order_status=ACTIVE)`
- `customer_deliveries_queryset()` — `OrderDelivery.objects.filter(order__customer=...)`
- `build_overview_metrics()` — counts only order-linked deliveries
- `build_activity_events()` — no subscription create/cancel events

**Result:** Subscribed customers without a legacy active Order show empty Active Order tab and incomplete meal/metric data.

### Database relationships (relevant subset)

```
User (1:1) CustomerProfile [public_id]
  ├── CustomerAddress (present/permanent)
  ├── Wallet (1:1) → WalletTransaction
  ├── Order [legacy, related_name=meal_orders]
  │     └── OrderDelivery (order FK, nullable)
  └── CustomerSubscription [current, related_name=meal_subscriptions]
        └── OrderDelivery (subscription FK, nullable)

MealCategory (is_subscribable=True) = subscription plan
OrderDelivery.status: scheduled | delivered | skipped | missed
CustomerSubscription.status: active | cancelled
```

No separate `SubscriptionPlan` model — plan is `MealCategory`.

### Frontend ↔ backend field mismatches (bugs, no fake data)

| UI area | Frontend expects | Backend returns | Impact |
|---------|------------------|-----------------|--------|
| Order history key | `order_public_id` | `public_id` | React key fallback |
| Order meal counts | `delivered_meals`, `skipped_meals` | `delivered_count`, `skipped_count` | Shows **0** |
| Meal history key | `delivery_public_id` | `public_id` | Key fallback |
| Addresses | `address`, `street` | `full_address`, `area`, `city`, … | Shows **"—"** |
| Allergies | `customer.allergies` | `has_allergy`, `allergy_details`, `restricted_foods` | Shows **"—"** |
| Overview profile | partial fields | full profile on API | Most fields hidden |

These are frontend contract bugs — fix by aligning types/UI to backend serializers, not by inventing data.

### Missing data for true Customer 360

| Data | Status | Source gap |
|------|--------|------------|
| Active subscription | ❌ Missing | Backend uses `get_active_order()` only |
| Subscription history | ❌ Not nested | Exists at `/api/v1/web/subscriptions/` with `customer_public_id` filter but not under customer detail |
| Subscription-scoped meals | ⚠️ Partial | `customer_deliveries_queryset` ignores `subscription` FK |
| Wallet overview totals | ⚠️ Partial | Detail has balance; no recharge/withdraw aggregate sub-resource |
| Manual funding review link | ❌ Not linked | `/api/v1/web/wallet-funding/` separate |
| Delivery places / location pref | ❌ Not exposed | Models exist, not in admin customer API |
| Payment gateway | ❌ Out of scope | `PaymentIntent` not mounted |
| Unified audit log | ❌ Composed only | `UserActivityLog` unused |

## Goals / Non-Goals

**Goals:**

- Admin opens one customer detail page and sees accurate subscription-first lifecycle
- Replace Order terminology in admin customer UI with Subscription/Service
- Fix data accuracy: subscription active tab, subscription-aware meal history, corrected metrics
- Fix known frontend/backend field mismatches
- Enrich Overview tab with profile fields already returned by API
- Add Wallet Overview summary (balance + aggregates + pending manual funding)
- Extend activity timeline with **confirmed** subscription/wallet/meal events only
- Enforce lean overview API (no nested history in detail response)
- Strong object-level permission tests (customer cannot read another customer's admin data)
- Update backend + frontend docs and tests
- Phased delivery: backend contract first, then frontend tab rename/redesign

**Non-Goals:**

- Admin write actions (ban, edit profile, force-verify)
- Removing legacy Order records from database or admin order management (`/api/v1/web/orders/`)
- Payment gateway integration in customer 360
- Onahar/charity, device tokens, login history
- Mobile admin customer views
- Big-bang monolithic refactor of `AdminCustomerDetailPage.tsx` into many components (incremental extraction OK)
- Starting implementation before user confirms this plan

## Decisions

### 1. Subscription is the admin customer "service record"

**Choice:** Admin customer detail treats `CustomerSubscription` as the customer's active service and history record. Legacy `Order` rows remain queryable for pre-migration customers but are not the primary UI concept.

**Why:** Matches business rule stated by product: "Customer subscribes package = customer has active service/order."

**Alternative:** Keep Order tabs and add subscription as secondary — rejected (confusing, duplicates mental model).

### 2. New nested admin routes; deprecate order-centric routes

**Choice:**

| New (primary) | Replaces | Notes |
|---------------|----------|-------|
| `GET .../active-subscription/` | `.../active-order/` | Returns `{ "active_subscription": {...} \| null }` |
| `GET .../subscriptions/` | `.../orders/` | Paginated subscription history |
| `GET .../wallet-overview/` | (new) | Balance + aggregate totals |

Keep `active-order` and `orders` as deprecated aliases for one release with `Deprecation` header pointing to new paths.

**Why:** Clear contract break with escape hatch for any external consumers.

**Alternative:** In-place response shape change on existing paths — rejected (silent breaking change).

### 3. Subscription-aware delivery queries

**Choice:** Centralize customer delivery queryset:

```python
OrderDelivery.objects.filter(
    Q(order__customer=customer) | Q(subscription__customer=customer)
)
```

Apply to meals, meal-offs, metrics, and activity.

**Why:** `OrderDelivery` is the shared slot model post-migration; dual-parent is already in schema.

### 4. Reuse `get_active_subscription()` from orders service layer

**Choice:** Import `orders.services.subscription_service.get_active_subscription` in `admin_customer.py`; do not duplicate query logic.

**Why:** Single source of truth; respects DB unique constraint on active subscription per customer.

### 5. Detail overview payload shape (lean aggregation)

**Choice:** `GET /api/v1/web/customers/{public_id}/` returns **only**:

| Section | Contents |
|---------|----------|
| `profile` | Identity, addresses, profile fields, account/verification status |
| `summary` | Aggregate metrics (see Decision 11) |
| `active_subscription` | Nullable summary object (same shape as active-subscription action, not full nested deliveries) |
| `wallet_summary` | Nullable compact wallet totals (available balance, pending recharge/withdraw — see Decision 12) |

**Performance rule (MUST):**

- Overview MUST NOT include paginated history arrays: no `subscriptions[]`, `meals[]`, `wallet_transactions[]`, or `activity[]` embedded in the detail response
- All history MUST load via lazy tab endpoints with pagination
- Overview queries MUST avoid N+1 on history tables (prefetch only what summary needs)

**Why:** Customer detail page opens frequently; embedding history causes slow first paint and duplicate data transfer when tabs lazy-load anyway.

**Deprecated on detail (temporary):** `active_order` field may remain for backward compatibility but MUST NOT be primary.

### 6. List filter additive migration

**Choice:** Add filters:

| Filter | Purpose |
|--------|---------|
| `has_active_subscription` | Primary active-service filter |
| `has_wallet` | Customer has wallet row |
| `has_pending_recharge` | Pending manual recharge request exists |
| `subscription_expiring_soon` | Active subscription end/renewal within documented window |
| `inactive_subscription` | Has subscription history but no active subscription |

Keep `has_active_order` as deprecated alias. List item `current_package` prefers active subscription.

### 7. Frontend tab structure (target)

| # | Tab | Endpoint |
|---|-----|----------|
| Header | Summary cards | From detail `summary` + `active_subscription` + `wallet_summary` |
| 1 | Overview | Detail GET |
| 2 | Active Subscription | `active-subscription/` |
| 3 | Subscription History | `subscriptions/` |
| 4 | Meal History | `meals/` (subscription-aware after backend fix) |
| 5 | Meal-offs | `meal-offs/` |
| 6 | Wallet Overview | `wallet-overview/` |
| 7 | Wallet History | `wallet-transactions/` |
| 8 | Activity | `activity/` |

Remove "Active order" and "Order history" labels.

**Legacy orders (migration period):** Show a collapsible **"Legacy monthly orders"** section **only when** the customer has at least one legacy `Order` row (pre-migration). Section is collapsed by default, loads via deprecated `GET .../orders/` on expand. Hidden entirely when no legacy orders exist — subscription remains primary.

### 8. Frontend field alignment (no backend rename for counts)

**Choice:** Update frontend types to use `delivered_count`, `skipped_count`, `public_id`, `full_address`, allergy fields from API.

**Why:** Backend serializers are source of truth; frontend drift caused visible bugs.

### 9. Activity feed composition (confirmed events only)

**Choice:** Compose activity from **explicit, confirmed domain signals** only. Allowed `event_type` values:

| event_type | Source |
|------------|--------|
| `subscription_created` | `CustomerSubscription.created_at` |
| `subscription_cancelled` | documented cancel timestamp on subscription |
| `wallet_transaction_completed` | `WalletTransaction` where `status=completed` |
| `meal_delivered` | `OrderDelivery` where `status=delivered` and status transition is recorded (use `delivered_at` or first transition to delivered — NOT bare `updated_at`) |
| `meal_skipped` | `OrderDelivery` where `status=skipped` with skip recorded |
| `order_created` / `order_status_changed` | legacy `Order` / `OrderStatusHistory` only |

**MUST NOT:** Infer events from `OrderDelivery.updated_at` alone — updates may occur for non-lifecycle reasons (address change, admin correction, etc.).

Sort by `occurred_at` desc; paginate via `/activity/`.

### 10. Subscription status handling

**Choice:** Backend serializers expose `status` as the model's current choice value (from `CustomerSubscription.Status` or equivalent). Frontend MUST render status labels from API response and tolerate unknown/new enum values gracefully (display raw value, no hardcoded enum-only UI).

**Why:** Future statuses (`pending`, `expired`, `paused`, `completed`) may be added without frontend deploy.

### 11. Summary cards / overview metrics

**Choice:** Detail `summary` MUST include at minimum:

| Field | Purpose |
|-------|---------|
| `total_subscriptions` | Count of subscription records |
| `total_meals_delivered` | Subscription + legacy order deliveries |
| `total_meal_offs` | Skipped deliveries |
| `customer_lifetime_value` | Documented CLV — default: sum of completed wallet payment debits (`total_wallet_spent`) unless product defines otherwise |
| `last_payment_at` | Latest completed wallet payment debit timestamp |
| `last_meal_delivered_at` | Latest delivered delivery slot timestamp |
| `current_package_expires_at` | From active subscription end date or documented renewal boundary; null when open-ended |
| `wallet_balance` / `wallet_currency` | Current spendable balance |
| `last_activity_at` | Max of confirmed activity timestamps |

Header cards on frontend: Active Subscription, Wallet Balance, Meals Delivered, Total Subscriptions, Customer Lifetime Value, Last Payment Date, Last Meal Date, Current Package Expiry.

### 12. Wallet overview (manual funding aware)

**Choice:** `GET .../wallet-overview/` and compact `wallet_summary` on detail include:

| Field | Meaning |
|-------|---------|
| `available_balance` | Current spendable wallet balance |
| `pending_recharge_amount` | Sum of pending manual recharge requests |
| `pending_withdraw_amount` | Sum of pending manual withdraw requests (reserved) |
| `total_recharged` | Sum of completed recharge credits |
| `total_withdrawn` | Sum of completed withdraw debits |
| `total_spent` | Sum of completed payment debits |

**Support scenario:** User says "I recharged but balance didn't update" — admin sees `pending_recharge_amount: 500 BDT` on Wallet Overview without opening wallet-funding queue.

Integrates with `manual-recharge-withdraw` pending transaction model. Link to `/admin/wallet-funding` queue remains optional secondary action.

### 13. Object-level permission isolation

**Choice:** All admin customer endpoints enforce `IsVerifiedAdmin` **and** reject authenticated non-admin users with `403`, including when a customer JWT attempts to read another customer's `public_id`:

```
Customer A token → GET /api/v1/web/customers/{customer-B-public-id}/ → 403
```

Same rule applies to all nested sub-resources. Tests MUST prove cross-customer access is denied.

### 14. Implementation phasing (requires user confirmation before Phase 2+)

| Phase | Scope | Repo |
|-------|-------|------|
| **Phase 1** | Analysis + this OpenSpec change | Done |
| **Phase 2** | Backend subscription-first APIs + tests | befood-backend |
| **Phase 3** | Frontend tab rename + field fixes + wallet overview | befood-frontend |
| **Phase 4** | Docs, OpenAPI, QA pass | Both |

Do not start Phase 2 until user confirms.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Deprecated routes still used by stale frontend deploy | Keep aliases + Deprecation headers; coordinate frontend deploy after backend |
| Mixed customers (legacy Order + new Subscription) | Dual-parent delivery query; overview shows subscription first, legacy order in summary counts separately |
| Large meal history performance | Existing pagination; ensure indexes on `OrderDelivery(service_date, subscription_id, order_id)` |
| Breaking admin API consumers | Additive fields first; deprecate don't delete in v1 |
| Frontend monolith hard to maintain | Extract tab components incrementally during Phase 3 |
| Manual funding txs not obvious in wallet tab | Wallet overview includes `pending_recharge_amount` / `pending_withdraw_amount`; wallet history includes review status on txn rows |
| Overview response bloat | Explicit rule: no history arrays in detail; lazy paginated endpoints only |
| Inferred activity events from updated_at | Confirmed-event allowlist only; no updated_at inference |

## Migration Plan

1. Deploy backend with new endpoints + deprecated aliases (no frontend change required yet)
2. Deploy frontend tab/field updates
3. Monitor deprecated endpoint usage; remove aliases in follow-up change after confirmation
4. Rollback: frontend can temporarily call deprecated paths; backend aliases remain until removal change

## Resolved decisions (formerly open questions)

1. **Legacy orders UI:** Collapsible "Legacy monthly orders" section, **only when** customer has legacy `Order` rows; collapsed by default; subscription primary.
2. **Wallet overview scope:** Pending manual funding amounts inline on wallet overview; optional link to wallet-funding queue for approve/reject actions.
3. **Delivery places:** Defer to follow-up change (out of scope for v1).
4. **Deprecated alias timeline:** Keep `active-order` / `orders` aliases for one release with `Deprecation` headers.

## Open Questions

(none blocking — proceed to Phase 2 on stakeholder confirmation)

---

## Appendix: Current API endpoint inventory

### Admin customer (existing)

| Method | Path |
|--------|------|
| GET | `/api/v1/web/customers/` |
| GET | `/api/v1/web/customers/{public_id}/` |
| GET | `/api/v1/web/customers/{public_id}/active-order/` |
| GET | `/api/v1/web/customers/{public_id}/orders/` |
| GET | `/api/v1/web/customers/{public_id}/meals/` |
| GET | `/api/v1/web/customers/{public_id}/meal-offs/` |
| GET | `/api/v1/web/customers/{public_id}/wallet-transactions/` |
| GET | `/api/v1/web/customers/{public_id}/activity/` |

### Related (not nested under customer today)

| Method | Path |
|--------|------|
| GET | `/api/v1/web/subscriptions/?customer_public_id=` |
| GET | `/api/v1/web/subscriptions/{public_id}/` |
| GET | `/api/v1/web/wallet-funding/requests/` |

### Customer-facing (unchanged)

| Method | Path |
|--------|------|
| POST | `/api/v1/subscriptions/` |
| GET | `/api/v1/subscriptions/current/` |
| GET | `/wallet/`, `/wallet/transactions/` |

## Appendix: Step-by-step implementation plan

### Backend (`befood-backend`)

1. Add `build_active_subscription_payload()` using `get_active_subscription()`
2. Add `customer_subscriptions_queryset()` with annotations (delivered/skipped counts)
3. Refactor `customer_deliveries_queryset()` to dual-parent filter
4. Update `build_overview_metrics()` for subscription-aware counts + wallet aggregates
5. Extend `build_activity_events()` with subscription events
6. Add serializers: `AdminCustomerActiveSubscriptionSerializer`, `AdminCustomerSubscriptionHistorySerializer`, `AdminCustomerWalletOverviewSerializer`
7. Add ViewSet actions: `active_subscription`, `subscriptions`, `wallet_overview`
8. Mark `active_order`, `orders` actions deprecated; add response headers
9. Update list filter `has_active_subscription`
10. Tests: subscription customer shows active subscription; meal history includes subscription deliveries; metrics accuracy; permission/auth unchanged
11. OpenAPI + `user_management/docs/backend/admin-customer-management.md`

### Frontend (`befood-frontend`)

1. Update types to match backend field names
2. Add API functions + hooks for new endpoints
3. Rename tabs; remove Active order / Order history
4. Build Active Subscription + Subscription History tab components
5. Add Wallet Overview tab
6. Fix Overview: addresses, allergies, full profile fields
7. Add header summary cards from detail payload
8. Loading skeleton / empty states per tab
9. Manual QA with subscribed + legacy order test customers

### Verification checklist

**API performance**

- [ ] Detail overview response contains profile + summary + active_subscription summary + wallet_summary only — no history arrays
- [ ] History tabs load via paginated sub-resources

**Permission isolation**

- [ ] Unauthenticated → 401
- [ ] Non-admin authenticated → 403
- [ ] Customer A token cannot read Customer B detail or nested resources → 403

**Customer scenarios (QA matrix)**

| Customer | Profile | Expected |
|----------|---------|----------|
| **A** | Active subscription, wallet, delivered meals | All summary cards populated; active subscription non-null; meal/wallet/activity tabs have data |
| **B** | Cancelled subscription(s), no active | Subscription history populated; `active_subscription: null`; empty state on Active Subscription tab |
| **C** | No subscription, no wallet | Empty states throughout; overview nulls documented; no fake data |
| **D** | Legacy order only (pre-migration) | Subscription primary empty; Legacy orders collapsible section visible on expand; meal history includes legacy deliveries |

**Data accuracy**

- [ ] Subscribed customer shows active subscription (not empty)
- [ ] Meal history includes subscription deliveries
- [ ] Summary cards match wallet + meal reality
- [ ] Wallet overview shows pending recharge when manual funding pending
- [ ] Activity feed shows only confirmed events (no spurious delivery updates)
- [ ] Subscription status rendered from API value (tolerates unknown enums)
- [ ] Pagination on all history tabs
