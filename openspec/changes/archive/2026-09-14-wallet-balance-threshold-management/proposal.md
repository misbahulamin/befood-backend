## Why

Today BeFood only exposes one wallet threshold (`min_wallet_balance_to_order`) that gates new subscriptions. Once subscribed, customers with declining balances receive no proactive reminder, and meal delivery keeps retrying until charge fails per slot—without a clear “meal service stopped” state or an ops-facing low-balance report. Admins need three ordered thresholds plus automated twice-daily enforcement so customers recharge earlier and kitchen/ops stop chasing unpaid meals.

## What Changes

- Extend the existing order-wallet settings singleton with two new BDT thresholds: **low-balance reminder** and **meal-stop**, alongside the existing **subscription minimum**.
- Enforce a strict ordering rule on admin updates: subscription minimum > low-balance reminder > meal-stop (all ≥ 0, max two decimal places).
- Add a production-ready managed cron job that runs twice daily (08:00 and 20:00 Asia/Dhaka) to evaluate verified active customers’ spendable wallet balances.
- When balance is below the reminder threshold (and not already meal-stopped), send customer push notification and branded email (idempotent per day/threshold band where practical).
- When balance is below the meal-stop threshold, stop future meal processing for that customer (system skip / block future deliveries without breaking manual admin mark-delivery flows), and notify the customer by push + email.
- After each cron run, email verified admins a structured low-balance / meal-stopped user report (name, phone, package, balance, address, meal status).
- Update Admin Frontend Settings UI so verified admins can view/edit all three thresholds with client-side and API validation.
- Reuse existing wallet ledger, notification (FCM), email branding, verified-admin access, and managed-cron installer patterns. **Do not** modify GitHub CI/CD deploy YAML.

## Capabilities

### New Capabilities

- `wallet-low-balance-reminder`: Detect balances below the reminder threshold and send customer push + email reminders.
- `wallet-meal-stop`: When balance falls below the meal-stop threshold, block future meal delivery processing and notify the customer; preserve manual admin delivery flows.
- `wallet-balance-threshold-cron`: Twice-daily managed cron orchestration that evaluates active verified customers, applies reminder/stop actions, and triggers the admin summary.
- `admin-low-balance-summary`: Professional structured admin email listing affected users (name, phone, package, balance, address, meal status).
- `wallet-threshold-admin-frontend`: Admin Settings UI and API client updates for configuring and validating the three thresholds.
- `managed-cron-install`: Extend the managed crontab installer to register the twice-daily wallet-threshold jobs (08:00 / 20:00 Asia/Dhaka) inside the existing `# BEGIN/END BEFOOD-MANAGED` block without changing deploy YAML.

### Modified Capabilities

- `order-wallet-min-balance-settings`: Extend the singleton and verified-admin GET/PATCH contract with `low_balance_reminder_threshold` and `meal_stop_threshold`, plus cross-field ordering validation; keep subscription-minimum semantics for subscribe eligibility.

## Impact

- **Backend models/API:** `orders.models.OrderWalletSettings`, `OrderWalletSettingsSerializer`, `OrderWalletSettingsView`, `orders/services/order_wallet_settings.py`; customer wallet read path may expose the new thresholds for UX.
- **Meal delivery eligibility:** `orders/services/auto_meal_delivery.py` (and related delivery queryset / subscription state) must respect meal-stop without changing charge ledger semantics in `meal_payment` / `debit_wallet`.
- **Notifications/email:** Reuse `notifications/services/fcm_service.py`, branded email templates (`user_management/services/email_branding.py`), and admin recipient resolution similar to `wallet/services/funding_notifications.py`.
- **Cron:** New management command + wrapper script; update `scripts/cron/install_managed_cron.sh` only (no `.github/workflows/deploy.yml` edits).
- **Frontend:** `AdminSettingsPage.tsx`, `adminOrderWalletSettingsApi.ts`, `orderWalletSettingsTypes.ts`.
- **Docs/tests:** Backend docs under `orders/docs/` / `wallet/docs/` as needed; unit/API tests for settings validation, cron actions, and notification/email triggers.
- **Non-goals:** Per-plan thresholds; changing subscribe debit behavior; editing CI/CD YAML; replacing manual meal-off or admin mark-delivery.
