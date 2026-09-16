## Why

Customers blocked by low-balance meal-stop stay blocked after admin-approved recharge because `approve_recharge` credits the wallet inline and never runs the meal-stop resume helper used by `credit_wallet`. Separately, meal-stop cron today notifies primarily on **transition to blocked**, so a customer who remains under `meal_stop_threshold` across the twice-daily cron may not get a repeated low-balance warning push on every run.

## What Changes

- On successful admin approval of a **pending** customer recharge, after wallet credit, call `maybe_resume_after_wallet_credit(profile)` and use its **boolean** return as `meal_service_restored` (no second balance/flag query for the API field).
- Resume clears `meal_service_blocked_low_balance` / `meal_service_blocked_at` only when post-credit spendable balance (same source as cron: `spendable_balance` → `Wallet.balance`) is `>=` live `meal_stop_threshold`.
- Insufficient credit, pending, and rejected recharges do not clear the block.
- **No DB migration** — resume uses existing profile fields only.
- **No new “meal service restored” customer notification** — existing recharge-approved push/email stay; resume is silent to the customer.
- Admin approve response adds additive `meal_service_restored`; customer apps unchanged; admin UI optional toast when `true`.
- On each wallet-threshold cron evaluation where spendable balance is strictly below `meal_stop_threshold`, send the **Low Wallet Balance Alert** customer push (allowed twice per day with the twice-daily cron). **Do not** gate this push with `last_low_balance_reminder_on`. Meal-stop **block** application remains unchanged and separate from the push.
- Existing once-per-day reminder path for the higher `low_balance_reminder_threshold` band stays as-is unless product later consolidates it.

## Capabilities

### New Capabilities
- `meal-service-resume-on-recharge-approval`: After admin-approved pending recharge credits the wallet, clear low-balance meal-stop when post-credit spendable balance meets the live threshold; expose `meal_service_restored` from the helper’s boolean return; no restore notification; no migration.
- `meal-stop-low-balance-cron-push`: On every threshold-cron pass where balance is below `meal_stop_threshold`, send the specified low-wallet-balance warning push without daily idempotency; keep block/resume/cron scheduling semantics otherwise intact.

### Modified Capabilities
- _(none)_ in `openspec/specs/` — behavior is captured in the new delta capabilities above.

## Impact

- **Services:** `wallet/services/funding.py` (`approve_recharge`); `orders/services/wallet_balance_thresholds.py` (cron meal-stop branch notify frequency); `notifications/services/wallet_threshold_notifications.py` (push title/body for meal-stop-band warning).
- **Balance source:** Must stay `spendable_balance(customer)` → `Wallet.balance` (no `available_balance` field on Wallet).
- **API:** Admin funding approve + serializer/OpenAPI for `meal_service_restored`.
- **Unchanged:** Auto meal delivery skip-on-block; reject/pending/withdraw approve; customer submit recharge; schema/migrations.
- **Frontend:** Customer none; admin optional “Meal service restored” when `meal_service_restored === true`.
- **Tests / docs:** Approve resume cases; cron push twice same day while still below threshold; funding + threshold docs.
