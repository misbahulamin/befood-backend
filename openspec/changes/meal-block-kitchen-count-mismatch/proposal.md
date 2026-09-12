## Why

After lunch auto-delivery charges wallets at 15:00 Asia/Dhaka, customers whose spendable balance falls below `meal_stop_threshold` stay unblocked until the 20:00 wallet-threshold cron. Kitchen Today cooking counts exclude only the `meal_service_blocked_low_balance` flag, so dinner cook headcount stays inflated (observed 25 → 23 after 20:00) and kitchen may cook for customers who will not be auto-delivered at 23:00.

## What Changes

- After a successful meal-delivery wallet debit (auto-delivery and operator mark-delivered), immediately evaluate `meal_stop_threshold` and apply `meal_service_blocked_low_balance` using the same rules as the wallet-threshold cron.
- Keep the existing 08:00 / 20:00 Asia/Dhaka `check_wallet_balance_thresholds` cron for reminders, resume, admin summary, and non-charge balance drift — do not remove it.
- Reuse shared threshold helpers (`apply_meal_service_block` / spendable balance vs `OrderWalletSettings.meal_stop_threshold`); no new block flags or settings fields.
- Add tests proving lunch charge that drops balance below threshold blocks the customer before the evening cron, and that Kitchen Today `final_cooking_count` drops accordingly.
- Document the corrected meal lifecycle (slot creation ≠ 15:00 deliver; block is flag-based, not live-balance in kitchen demand).
- No **BREAKING** API contract changes; Kitchen / Meal Close / wallet settings endpoints stay the same.

## Capabilities

### New Capabilities

- `post-meal-charge-meal-stop`: After a successful meal-payment debit, evaluate spendable balance against `meal_stop_threshold` and immediately set or keep `meal_service_blocked_low_balance` (with the same stop semantics as the twice-daily wallet-threshold job).

### Modified Capabilities

- `meal-delivery-wallet-payment`: Successful delivered-meal debit MUST trigger post-charge meal-stop evaluation; insufficient-funds failure paths remain unchanged and MUST NOT leave a successful charge without evaluation when charge succeeds.
- `kitchen-cooking-requirement`: Clarify that `final_cooking_count` continues to exclude customers with `meal_service_blocked_low_balance=true`, and that post-charge blocking MUST make those customers disappear from cook counts without waiting for the 20:00 cron (no live-balance formula change in this change).

## Impact

- **Services:** `orders/services/auto_meal_delivery.py`, `orders/services/meal_payment.py` / `order_delivery.py` mark-delivered path, `orders/services/wallet_balance_thresholds.py` (shared evaluate helper), possibly thin hooks after `debit_wallet` meal-payment success only (not all wallet debits).
- **Cron:** No schedule change required for the fix; 08:00/20:00 wallet check and 15:00/23:00 auto-deliver remain. Optional later hardening (extra 15:05 cron) is out of scope if post-charge evaluation ships.
- **APIs:** No new endpoints; Kitchen Today and Meal Close behavior improve because the block flag updates earlier.
- **DB:** No migration — `CustomerProfile.meal_service_blocked_low_balance` and `OrderWalletSettings.meal_stop_threshold` already exist.
- **Tests / docs:** Auto-delivery, wallet threshold, meal demand kitchen tests; backend/frontend meal-demand or wallet-threshold docs noting the 15:00→20:00 gap is closed by post-charge evaluation.
