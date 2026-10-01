## Why

Active BeFood subscribers sometimes need extra meals for guests beyond their regular subscription entitlement. Today the backend has no prepaid, quota-limited, cutoff-aware path to sell those extras while reusing canonical subscription eligibility, published slot pricing, meal-off deadlines, wallet ledger debit, and meal-stop threshold rules—so guest meals cannot be sold safely without duplicating core domain logic.

## What Changes

- Allow an **active subscriber** to order one or more **Guest Meals** for a specific Asia/Dhaka business `date` + `meal_period` (`lunch` | `dinner`), subject to package/subscription period coverage, published menu slot availability, and existing meal-off cutoff.
- Price each guest unit as **canonical published slot meal price + configurable one-time guest box price**; snapshot pricing on the guest order so later package/box price changes do not rewrite history.
- Debit the customer wallet **at order time** (prepaid) inside an atomic transaction with meal-stop floor enforcement; never trust client-supplied prices, balances, or subscription ids.
- Enforce a **calendar-month maximum of 10 guest meal units** (quantity-based, Asia/Dhaka), computed from authoritative guest-order records—not a lone mutable counter.
- Expose customer APIs for **usage**, **preview** (read-only quote), and **create**, plus delivery/kitchen/rider representation of guest quantity without inventing a parallel delivery lifecycle.
- Add admin-configurable **guest meal box price** (and optionally monthly limit) on the existing order-wallet settings singleton pattern.
- Extend Customer 360 activity composition with a `guest_meal_ordered` event when guest meals are successfully created.
- **Non-goals (this change):** Guest Meal cancellation/refund implementation (open business decision only); non-subscriber guest meals; hardcoding meal or box prices in application constants.

## Capabilities

### New Capabilities

- `guest-meal-order`: Eligibility, pricing, monthly quota, wallet debit + meal-stop floor, preview/create/usage APIs, pricing snapshots, concurrency/idempotency rules.
- `guest-meal-delivery-integration`: How guest quantity attaches to existing `OrderDelivery` / rider board / kitchen demand without a duplicate delivery status machine.
- `guest-meal-settings`: Admin-configurable guest box price (and optional monthly limit) via `OrderWalletSettings`-style singleton.

### Modified Capabilities

- `admin-customer-history`: Compose `guest_meal_ordered` (and optionally future cancel/refund) into the admin activity feed.
- `meal-demand-forecasting`: Cooking/demand counts MUST include guest meal quantities for the slot when guest orders are active for kitchen planning.
- `meal-delivery-wallet-payment`: Clarify that prepaid guest-meal debits are a separate ledger purpose from charge-on-delivery regular meals; regular delivery charge path remains unchanged for the subscriber’s own slot.

## Impact

- **Orders app:** new `GuestMealOrder` (or equivalent) model + service orchestration; thin API views/serializers under `/api/v1/...`; docs under `orders/docs/`.
- **Wallet:** reuse `debit_wallet` / idempotency; new transaction metadata/purpose (and possibly `WalletTransaction.Type` value) for guest meal payment; threshold check aligned with product rule.
- **Meals:** reuse `resolve_published_slot_for_delivery` / `final_meal_price_snapshot` only—no duplicate pricing engine.
- **Meal-off:** reuse `is_past_meal_cutoff` / `meal_off_deadline` / `business_today`.
- **Subscription:** reuse `get_active_subscription` + `periods_for_meal_period(subscription.meal_period_snapshot)`.
- **Delivery / rider / kitchen:** today-board, demand, and related serializers need guest quantity visibility.
- **Admin Customer 360:** activity + optional subscription/order detail surfaces.
- **Tests:** unit, API, concurrency, and delivery-integration coverage as listed in design/tasks.
- **No BREAKING** changes to existing subscribe, meal-off, or charge-on-delivery contracts if guest APIs are additive.
