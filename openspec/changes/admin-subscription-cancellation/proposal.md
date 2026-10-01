## Why

Production BeFood already lets customers cancel via `POST /api/v1/subscriptions/current/cancel/`, but verified admins cannot cancel from Customer 360 (`/admin/customers/{public_id}`). Support must either ask the customer to cancel or work around the gap. Worse, the shared cancel service keeps **all same-day** slots and withdrawable balance always subtracts `meal_stop_threshold` regardless of subscription status—so post-cancel refunds and peri-cutoff lunch/dinner handling do not match the intended business rules (independent lunch/dinner cutoff, threshold exemption after cancel, retain finalized-meal liability).

## What Changes

- Add a **verified-admin** cancel (and optional preview) path on admin customer 360, reusing one **canonical** `cancel_subscription` domain service shared with customer self-cancel.
- **Enhance** `cancel_subscription` so each `SCHEDULED` slot is classified with existing `is_past_meal_cutoff` (`now > deadline` = finalized/preserve; at-or-before deadline = cancellable → `SKIPPED`/`system`). Soft-skip only; no hard-delete; never alter `delivered` / already `skipped` / charged rows.
- **Change withdrawable math** so:
  - **Active** subscribers: keep `max(0, recharge_balance − meal_stop_threshold)`.
  - **No active subscription** (including after cancel): do **not** apply meal-stop floor; instead reserve estimated charge for still-`SCHEDULED` finalized (past-cutoff) meals using published slot pricing.
- Frontend: Cancel Subscription on Active Subscription tab with confirmation modal; all impact numbers from backend preview/response; invalidate customer 360 + subscription queries.
- Tests covering cutoffs, wallet liability, auth, idempotency, and concurrency-sensitive paths.
- Docs: backend + frontend technical notes for the new admin contract.

**BREAKING (customer self-cancel semantics):** Same-day slots that are still inside the meal-off window will now be system-skipped on cancel (today’s dinner can be cancelled if cancel is before dinner cutoff). Previously both lunch and dinner on `cancel_effective_on` stayed `scheduled`. This is intentional so admin and customer share one rule set.

Not breaking for active-subscriber withdraw caps or meal ON/OFF / charge-on-deliver flows.

## Capabilities

### New Capabilities

- `canonical-subscription-cancellation`: Shared cancel algorithm—lock subscription, Asia/Dhaka cutoff classification, soft-skip cancellable slots, set `cancelled_at` / `cancel_effective_on`, idempotent repeats, audit fields.
- `admin-customer-subscription-cancel`: Verified-admin cancel (+ optional preview) on customer 360 APIs, response payload for UI, activity/audit of admin actor.
- `cancelled-subscriber-withdrawable`: Withdrawable balance and `request_withdraw` validation after cancel—threshold exemption + finalized-meal liability from published slot prices.
- `admin-subscription-cancel-frontend`: Admin Customer Detail Cancel Subscription UX (modal, mutations, refresh, permissions gating).

### Modified Capabilities

- _(none formally delta’d)_ — no existing main spec documents day-granular cancel skip (`service_date__gt` only). Wallet meal-stop **block** rules stay; only withdrawable formula gains a cancelled-subscriber branch (covered by new `cancelled-subscriber-withdrawable`).

## Impact

- **Backend:** `orders/services/subscription_service.py` (`cancel_subscription`), `orders/api/subscription_views.py` / `user_management/api/admin_customer_views.py`, wallet `withdrawable.py` + `funding.request_withdraw` + `Wallet.withdrawable_balance`, serializers/OpenAPI, optional additive `CustomerSubscription` audit fields (`cancelled_by`, `cancel_source`), tests under `orders/tests/`, `wallet/tests/`, `user_management/tests/`.
- **Frontend (`befood-frontend`):** `AdminCustomerDetailPage`, `adminCustomerApi`, `useAdminCustomers`, new confirm modal; patterns from `CancelSubscriptionModal` / `AdminModal` / `sonner`.
- **Ops:** Deploy backend (and migration if audit columns added) before frontend; old frontend remains safe (no cancel button). Customer app self-cancel behavior changes when backend ships—coordinate release notes.
- **Systems preserved:** Meal ON/OFF, delivery board/rider mark, charge-on-deliver, pending withdraw reservation (already debited), kitchen demand skip semantics, activity feed `subscription_cancelled`.
