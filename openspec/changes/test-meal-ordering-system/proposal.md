# Proposal

## Why

BeFood needs a lifetime, limited **Test Meal** funnel so non-subscribers can try lunch/dinner before committing to a subscription. Guest Meal already covers prepaid extras for **active subscribers**; Instant Meal is display/pricing only. There is no production order path for authenticated non-subscribers with quota, manual payment, and Test→Subscription conversion analytics.

## What Changes

- Add a dedicated **Test Meal** order category (`TEST_MEAL`) with a new `TestMealOrder` model (and related payment/audit/funnel records), separate from Guest Meal and Instant Meal.
- Customer APIs: eligibility/quota, published packages, quote (slot price + configurable box charge), order create/history — **no wallet debit**, **no online payment**, confirm as `CONFIRMED` + `UNPAID` + `MANUAL`.
- Enforce lifetime quota of **2** accepted orders per customer identity, atomically; active subscribers always ineligible; cancelled/refunded orders still consume quota by default.
- Reuse published menu slot pricing (`final_meal_price_snapshot`), meal-off cutoff (`Asia/Dhaka`), customer address book/serviceability, and Public UUID conventions.
- Admin APIs: order list/detail/filters, manual payment recording with audit, conversion + funnel analytics, revenue split (confirmed value vs collected vs outstanding).
- Integrate Test Meal units into kitchen demand, deliveryman/ops board, and consolidated “meals served” reporting with an explicit third category (Subscription / Guest / Test) — without changing Guest Meal or subscription wallet charge semantics.
- Backend + OpenAPI + `orders/docs` contracts only in this change; **no Flutter or React Admin Panel code**.

## Capabilities

### New Capabilities

- `test-meal-order`: Customer eligibility, lifetime quota, package/date/period validation, quote, checkout with address snapshot, order history, idempotency, and Bengali/English reason messages.
- `test-meal-manual-payment`: Manual payment statuses, admin record/correct payment with audit trail, separation of order status vs payment status, and confirmed-value vs collected-revenue accounting.
- `test-meal-admin-api`: Verified-admin list/detail/search/filter APIs and chart-ready analytics aggregations for Test Meal orders and payments.
- `test-meal-conversion-analytics`: Test→Subscription conversion KPIs (delivered-first primary formula), time-to-convert, and privacy-conscious funnel event ingestion/dedup.
- `test-meal-ops-integration`: How Test Meal participates in kitchen demand, delivery board/today ops, and admin meals-served totals without double-counting or being mistaken for subscription/guest meals.
- `test-meal-frontend-docs`: Backend-authored Flutter and Admin Panel integration contracts (endpoints, payloads, error codes, workflows) without implementing those clients.

### Modified Capabilities

- `meal-demand-forecasting`: Demand/cooking counts MUST include countable Test Meal units for the slot, as a distinct category from subscription deliveries and Guest Meal quantities.
- `kitchen-cooking-requirement`: Kitchen today requirement MUST include Test Meal cooking headcount consistently with the shared demand service.

## Impact

- **Orders app:** new model(s)/migrations, `orders/services/test_meal*.py`, customer + admin API modules/URLs, settings fields on `OrderWalletSettings` (e.g. test meal box price + lifetime quota), tests, backend/frontend docs.
- **Meals:** reuse `MealCategory` (`is_active` + `is_subscribable` catalog), `resolve_published_slot_for_delivery` / `final_meal_price_snapshot` — no new Instant-style pricing.
- **User management / addresses:** reuse customer address book + serviceability; object-scoped address ownership checks.
- **Delivery zones / board / meal demand / admin dashboard:** additive Test Meal counting and board visibility; Guest Meal and subscription charge paths unchanged.
- **Wallet:** explicitly **out of create path** (no debit). Future online payment must be additive without redesigning the order core.
- **Clients:** Flutter CTA + Admin Wallet/Test Meal UI consume new APIs in a later phase; this change ships contracts only.
