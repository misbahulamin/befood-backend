## Why

Verified customers must not buy a second meal package for the same calendar month, and must keep a minimum wallet balance before placing an order so the business can rely on prepaid funds. Month-lock already exists in order creation, but it needs an audit plus tests; the wallet minimum gate and admin-configurable threshold do not exist yet.

## What Changes

- **Audit and harden** the existing same-month meal-package lock (`check_existing_monthly_lock` in order creation): confirm it blocks a second non-cancelled package for the target `order_month`, document the rule, and fill any gaps in API error handling or tests.
- **Add a pre-order wallet eligibility gate**: after month-lock passes, require the customer’s wallet balance to be at least an admin-configured minimum (default **500.00 BDT**) before `create_meal_order` succeeds.
- **Add admin-configurable order wallet settings** (singleton, same pattern as `MealOffSettings` / `MenuRevealSettings`): verified admin can view and update `min_wallet_balance_to_order` without a code deploy.
- Reject order creation with a clear validation error when balance is below the configured minimum (including missing wallet treated as zero, and frozen wallets as ineligible).
- This gate is an **eligibility check only** — it does **not** debit the wallet or complete order checkout payment (wallet payment remains out of scope).
- Add/update backend and frontend docs, OpenAPI examples, and automated tests for both month-lock and wallet-minimum flows.

## Capabilities

### New Capabilities
- `order-month-package-lock`: Same-month meal package exclusivity for verified customers — at most one non-cancelled package order per `order_month`; audit/verify existing behavior and lock the contract in specs.
- `order-wallet-min-balance`: Order creation requires wallet balance ≥ configured minimum; clear reject when insufficient or wallet frozen.
- `order-wallet-min-balance-settings`: Admin singleton settings for the minimum wallet balance required to place an order (default 500.00 BDT).

### Modified Capabilities
- (none)

## Impact

- **Orders:** `orders/services/order_service.py` (eligibility checks), serializers/views/OpenAPI, tests, docs; optional new settings model under `orders/` (or `wallet/` if preferred in design).
- **Wallet:** Read balance/status via existing `Wallet` model / ledger helpers; no funding API change; no payment debit on order.
- **Admin API:** New settings endpoint (GET/PATCH) for verified admins, plus Django admin registration.
- **Clients:** Customer app surfaces month-lock and insufficient-balance errors; admin panel edits the minimum amount.
- **Related (unchanged):** Wallet recharge/withdraw, gateway payment, and charging order total from wallet stay deferred.
