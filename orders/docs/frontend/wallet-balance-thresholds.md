# Wallet Balance Thresholds (Admin Frontend)

See also backend: `orders/docs/backend/wallet-balance-thresholds.md`.

## What changed

Admin Settings (`AdminSettingsPage`) manages three ordered BDT thresholds through:

`GET/PATCH /api/v1/web/orders/order-wallet-settings/`

| Field | Purpose |
|-------|---------|
| `min_wallet_balance_to_order` | Subscribe eligibility (inclusive) |
| `low_balance_reminder_threshold` | Reminder when balance is strictly below |
| `meal_stop_threshold` | Auto meal delivery pause when balance is strictly below |

UI blocks submit when ordering is invalid; API returns `400` for the same rule.

## Ops behavior (no admin Settings UI change)

- Twice-daily cron may send **Low Wallet Balance Alert** push every run while a customer remains below `meal_stop_threshold` (not once-per-day).
- Admin recharge **approve** may return `meal_service_restored: true` when that approve cleared meal-stop; optional toast “Meal service restored”. See `wallet/docs/frontend/manual-wallet-funding.md`.

## Auth

Verified admin only (`IsVerifiedAdmin`). The admin router already gates Settings behind admin auth.
