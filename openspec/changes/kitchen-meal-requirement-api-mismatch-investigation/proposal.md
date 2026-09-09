## Why

Production kitchen APIs (`GET /orders/kitchen/today-meal-requirement/` and `GET /orders/kitchen/today-order-details/`) show different meal/customer totals for the same calendar day when refreshed morning vs mid-day (e.g. 21 → 22). Kitchen staff need a reliable cook count; before changing billing or delivery creation, we must pin the root cause and a production-safe fix plan.

## What Changes

- **Investigation only in this change (no production behavior change until a follow-up apply of the fix):** document the full API → service → queryset → model flow, time-based mutation paths, cron/timezone/cache findings, and ranked root causes.
- Capture a **recommended production-safe fix contract** as specs (freeze / eligibility rules for kitchen counts) without editing runtime code in this change.
- Define **read-only production verification queries** operators can run to confirm which mid-day insert/unblock path actually moved the number on a given day.
- Explicitly out of scope for this change’s implementation: migrations, historical `OrderDelivery` deletes, wallet charge logic changes, breaking existing scheduled deliveries.

## Capabilities

### New Capabilities

- `kitchen-demand-count-stability`: Defines when kitchen cooking headcounts and order-details customer lists may change during a service day, how late subscription / meal-on / low-balance resume / menu-publish ensure interact with kitchen totals, and the intended freeze or eligibility rules after meal-off cutoff (so a follow-up implementation can be tested against a clear contract).

### Modified Capabilities

- `kitchen-cooking-requirement`: Clarify that the live kitchen requirement endpoint recalculates from `OrderDelivery` on every request (no day-start HTTP/Redis snapshot), and that default `meal_period` switches at `dinner_off_time` — so “mismatch” without explicit `service_date`/`meal_period` must be distinguished from true same-slot count drift.

## Impact

- **APIs (read analysis):** `/orders/kitchen/today-meal-requirement/`, `/orders/kitchen/today-order-details/`, and `/api/v1/web/...` aliases.
- **Services:** `orders.services.meal_demand` (`build_kitchen_requirement`, `build_kitchen_order_details`, `_demand_queryset`, `get_demand`), `orders.services.subscription_service` (`subscribe_customer`, `ensure_subscription_deliveries`), `orders.services.meal_off`, wallet threshold resume/block helpers, menu publish hook.
- **Models:** `OrderDelivery`, `CustomerSubscription`, `Order`, `MealOffSettings`, `CustomerProfile.meal_service_blocked_low_balance`.
- **Ops:** Managed cron (`auto_deliver_meals`, wallet threshold) — does **not** currently install `ensure_subscription_deliveries`; menu publish still calls ensure for all active subscriptions.
- **Non-impact (by design of this change):** no wallet debit path edits, no delivery status backfills, no HTTP response cache introduction unless a later fix chooses snapshot serving.
