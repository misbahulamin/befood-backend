# Design

## Context

See `proposal.md` for motivation. Observed baseline:

- **Guest Meal** (`GuestMealOrder` + `orders/services/guest_meal.py`): active subscribers only, monthly quantity quota, wallet debit at create, price = `final_meal_price_snapshot` + `OrderWalletSettings.guest_meal_box_price`, links to existing subscription `OrderDelivery`, Idempotency-Key, Asia/Dhaka + `is_past_meal_cutoff`.
- **Instant Meal**: published-slot projection with Instant profit % — **not** an order system; Test Meal must **not** reuse Instant pricing.
- **Active subscription**: `orders.services.subscription_service.get_active_subscription` (`CustomerSubscription.Status.ACTIVE`).
- **Packages**: `MealCategory` with `is_active` + `is_subscribable`; customer catalog already documented for subscriptions.
- **Addresses**: `customer/addresses` ViewSet + delivery place / serviceability; snapshots already exist on `OrderDelivery`.
- **Meal periods / money**: project uses lowercase `lunch`|`dinner` and `Decimal` quantized to `0.01` BDT.
- **Admin patterns**: `IsVerifiedAdmin`, page size 20/100 (see admin guest meal views).

Test Meal inverts Guest Meal eligibility (non-subscribers), uses lifetime order-count quota, and collects payment manually.

## Goals / Non-Goals

**Goals:**

- Mirror Guest Meal service/API layering (thin views, domain service, Public UUID, idempotency, settings on `OrderWalletSettings`) while keeping a separate model and routes.
- Create a fulfillment stop that ops/kitchen/board can see without requiring a subscription parent.
- Keep payment and delivery statuses independent; design payment fields for future online checkout without rewriting the order core.
- Document Flutter/Admin contracts in `orders/docs` only (no client repos).

**Non-Goals:**

- Flutter / React Admin Panel implementation.
- Online payment gateway or wallet debit for Test Meal in v1.
- Automatic quota restore on cancel/refund (admin audited restore may be a later change).
- `PARTIALLY_PAID` in v1.
- Changing Guest Meal, Instant Meal, or subscription wallet charge formulas.
- Treating Instant Meal cards as Test Meal orders.

## Decisions

### 1. Dedicated `TestMealOrder` model (not Guest Meal reuse)

**Choice:** New `orders.TestMealOrder` (`PublicIdMixin`) with package FK (`MealCategory`), customer FK, service_date, meal_period, special_instructions, price snapshots (`meal_price`, `box_charge`, `total_price`), currency, address FK + immutable address/window snapshots, `order_status`, `payment_status`, `payment_method`, timestamps, cancellation fields, `source_channel`, `idempotency_key` unique per customer.

**Why not extend Guest Meal:** Opposite eligibility, no subscription FK, no wallet txn, lifetime quota, package chosen by customer, manual payment fields, standalone delivery.

**Alternatives considered:** Polymorphic “extra meal” table — rejected (mixed invariants, harder admin filters).

### 2. Order vs payment status enums (project casing)

**Choice:** Persist lowercase snake enums consistent with Guest Meal / delivery:

| Concern | Values (v1) |
|---------|-------------|
| `order_status` | `confirmed`, `preparing`, `out_for_delivery`, `delivered`, `cancelled`, `failed` |
| `payment_status` | `unpaid`, `paid`, `refunded` |
| `payment_method` | `manual` (extensible later: `wallet`, `gateway`, …) |
| `meal_period` | `lunch`, `dinner` |

API docs may show uppercase aliases in product copy, but JSON enums follow existing `lunch`/`dinner` convention.

On successful customer create: `order_status=confirmed`, `payment_status=unpaid`, `payment_method=manual`. Skip a customer-visible `pending_payment` state because v1 confirms without collecting money first.

**Transitions:** Service-layer allow-list; invalid transitions raise domain errors. Delivered/cancelled/failed are terminal for fulfillment; payment may still change unpaid↔paid/refunded with audit.

### 3. Fulfillment via nullable `OrderDelivery.test_meal_order`

**Choice:** Add nullable FK `OrderDelivery.test_meal_order` → `TestMealOrder` (PROTECT/SET_NULL as appropriate). On confirm, create one `OrderDelivery` with `order=null`, `subscription=null`, `test_meal_order` set, status `scheduled`, address snapshots copied from selected place, logistics zone resolved from address serviceability. Parent exclusivity constraint: exactly one of (`order`, `subscription`, `test_meal_order`) non-null for new rows (migrate carefully for legacy order/subscription rows).

**Why:** Reuses board, mark-delivered, address snapshot, zone attribution paths with additive filters (`test_meal_quantity`) instead of a parallel logistics stack.

**Alternatives considered:** Self-contained logistics columns only on `TestMealOrder` — rejected (duplicates board/demand wiring). Attach to a fake subscription — rejected (corrupts subscription analytics).

**Mark delivered:** Extend existing admin/rider mark-delivered to update linked `TestMealOrder` → `delivered` **without** calling `charge_delivered_meal` / wallet debit. Payment remains independent.

### 4. Pricing and settings

**Choice:**

```
meal_price = published slot final_meal_price_snapshot(package, date, period)
box_charge = OrderWalletSettings.test_meal_box_price  # default 10.00
total = meal_price + box_charge
```

Resolve via `meals.services.slot_pricing.resolve_published_slot_for_delivery` (or equivalent package+date+period helper). Add settings: `test_meal_box_price`, `test_meal_lifetime_quota` (default 2). Reuse Guest Meal box admin surface pattern on order-wallet-settings — do **not** reuse Instant `profit_percent`.

Delivery windows as constants/settings returned by quote/eligibility helpers (lunch 11:00–14:00, dinner 19:30–22:30 Asia/Dhaka). Prefer settings if ops may tune later; otherwise module constants documented in API.

**Cutoff:** Reuse `is_past_meal_cutoff` + `business_today` (meal-off TZ).

### 5. Quota accounting and concurrency

**Choice:** Count accepted `TestMealOrder` rows for the customer excluding only never-persisted failures. Countable statuses = all successfully created rows including `cancelled`/`delivered`/`failed` after accept. Create path:

1. `transaction.atomic()`
2. Idempotency replay short-circuit
3. `select_for_update` on customer profile (or dedicated quota lock row) + lock existing test meal rows
4. Re-check active subscription, quota, slot, price, address ownership/serviceability
5. Persist `TestMealOrder` + `OrderDelivery` stop
6. No wallet calls

Idempotency: unique `(customer, idempotency_key)` partial constraint like Guest Meal.

### 6. Eligibility and profile gates

**Choice:** Eligibility reasons: `ACTIVE_SUBSCRIBER`, `QUOTA_EXHAUSTED`. Apply `PROFILE_INCOMPLETE` only if create would fail without required identity/phone/address under existing customer order rules — prefer requiring a serviceable address at create rather than full `profile_completed` boolean. `ACCOUNT_RESTRICTED` only if an existing account restriction flag already blocks ordering elsewhere.

Bengali quota message (product-provided) returned on eligibility and create rejection.

### 7. Manual payment and audit

**Choice:** Separate `TestMealPaymentEvent` (or JSON audit log table) recording record/correct/refund actions with actor, amounts, timestamps, notes. Order stores current `payment_status`, `amount_collected`, `paid_at`, `payment_notes`, `payment_recorded_by`. No automatic paid transition. Analytics: confirmed value = sum of confirmed order totals; collected = sum of paid amounts; outstanding = confirmed unpaid (and partial if added later).

### 8. Conversion and funnel

**Choice:** Compute conversion in a read service from `TestMealOrder` + `CustomerSubscription` history (first delivered test date vs first subscription `started_on` / activation timestamp). Persist nothing that can drift except optional cached annotations on admin serializers. Funnel: `TestMealFunnelEvent` with dedupe key `(event_name, correlation_id|customer_id, client_event_id)`; anonymous correlation id accepted until login links it. Do not backfill pre-instrumentation history.

### 9. API surface (backend phase)

Customer (authenticated verified customer), under `/api/v1/test-meals/`:

| Method | Path | Role |
|--------|------|------|
| GET | `eligibility/` | CTA gate |
| GET | `packages/` | catalog |
| POST | `quote/` | price only |
| POST | `orders/` | confirm |
| GET | `orders/` | history list |
| GET | `orders/{public_id}/` | detail |
| POST | `funnel-events/` | optional instrumentation |

Admin (verified admin), under `/api/v1/web/admin/test-meals/` (or project-consistent admin prefix):

| Method | Path | Role |
|--------|------|------|
| GET | `orders/` | list/filter |
| GET | `orders/{public_id}/` | detail |
| POST | `orders/{public_id}/record-payment/` | manual pay |
| GET | `analytics/` | KPIs + series |

Reuse existing address endpoints for add/list; create accepts `address_public_id`.

### 10. Ops / demand integration

**Choice:** Extend `meal_demand.get_demand` and board/today-summary similarly to Guest Meal additives: `test_meal_quantity` / include in `total_meal_quantity`. Admin dashboard `meals_served` gains `test_meals_served` and updates consolidated total = regular + guest + test. Profit ledger: **do not** auto-recognize Test Meal as wallet meal profit while unpaid; document outstanding decision if business wants cash-collected profit recognition later.

## Risks / Trade-offs

- [OrderDelivery parent constraint migration] → Careful CheckConstraint with legacy nullability; ship additive FK first, enforce exclusivity for new writes in service, then tighten DB constraint if safe.
- [Board/rider UI unaware of Test Meal] → Backend exposes fields now; client phase must render them — document clearly.
- [Unpaid delivered meals in kitchen counts] → Intentional for cooking; finance reports must use payment filters.
- [Quota never restores on cancel] → Product risk of “wasted” tries; mitigate later with audited admin restore only.
- [Conversion attribution edge cases (same-day subscribe)] → Spec separates pre-delivery vs post-delivery metrics; document date-range filters on analytics.

## Migration Plan

1. Add settings fields + `TestMealOrder` (+ payment events + funnel events) migrations.
2. Add nullable `OrderDelivery.test_meal_order` + indexes; deploy code that writes stops.
3. Mount customer/admin URLs; feature usable by API clients.
4. Extend demand/board/dashboard in same release to avoid undercounting once orders exist.
5. Rollback: disable routes via flag or URL unmount; leave tables (non-destructive). Do not reverse data-destroying migrations in production.

## Open Questions

- Whether collected manual payments should later write an `admin_wallet` / cash ledger entry (out of v1 create path; does not change order model).
- Whether Admin Panel hosts Test Meal under `/admin/wallet` or a dedicated `/admin/test-meals` route (frontend-only; APIs are independent).
- Exact package visibility rule if some `is_subscribable` plans should be Test-Meal-excluded (default: all active subscribable packages).
