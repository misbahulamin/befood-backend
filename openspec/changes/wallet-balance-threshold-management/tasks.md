## 1. Settings model & admin API

- [x] 1.1 Add `low_balance_reminder_threshold` and `meal_stop_threshold` to `OrderWalletSettings` with defaults `300.00` / `200.00`, migration, and Django admin display
- [x] 1.2 Extend `OrderWalletSettingsSerializer` + `update_order_wallet_settings` with merged cross-field validation: `min_wallet_balance_to_order > low_balance_reminder_threshold > meal_stop_threshold ≥ 0` (≤ 2 decimal places)
- [x] 1.3 Update OpenAPI examples on `OrderWalletSettingsView` and expose the two new fields on customer wallet GET read path
- [x] 1.4 Add/adjust API tests for defaults, valid PATCH, ordering conflicts, negative/precision rejection, and non-admin denial

## 2. Meal-stop customer state

- [x] 2.1 Add customer-level fields (`meal_service_blocked_low_balance`, `meal_service_blocked_at`, `last_low_balance_reminder_on`) with migration
- [x] 2.2 Implement apply-block / clear-block helpers in a wallet-threshold service module
- [x] 2.3 Exclude blocked customers from auto-delivery eligibility (`eligible_delivery_queryset` / equivalent) without changing admin mark-delivery APIs
- [x] 2.4 Hook auto-resume on successful wallet credit (and rely on cron as backup) when balance ≥ meal-stop threshold

## 3. Customer reminder & stop notifications

- [x] 3.1 Implement best-effort push helpers (`wallet_low_balance`, `wallet_meal_stop`) reusing FCM token resolution + `send_to_tokens`
- [x] 3.2 Add branded customer email templates for low-balance reminder and meal-stop
- [x] 3.3 Enforce at-most-once reminder per Asia/Dhaka business day; meal-stop notify primarily on transition to blocked

## 4. Admin summary email

- [x] 4.1 Build structured HTML table email (Name, Phone, Package, Current Balance, Address, Status) plus plain-text fallback
- [x] 4.2 Send to verified admin recipients via existing funding-admin email resolution pattern; isolate send failures from batch success
- [x] 4.3 Define empty-run behavior (short “no low-balance users” mail or skip) and document it

## 5. Cron orchestration

- [x] 5.1 Implement `orders.services.wallet_balance_thresholds.run_wallet_threshold_check` with meal-stop → resume → reminder priority, per-customer isolation, and `RunResult` summary
- [x] 5.2 Add `manage.py check_wallet_balance_thresholds [--dry-run]` printing structured stdout for cron logs
- [x] 5.3 Add `scripts/cron/run_wallet_threshold_check.sh` (venv, flock, log append under `logs/`)
- [x] 5.4 Extend `scripts/cron/install_managed_cron.sh` managed block with `0 8` and `0 20` Asia/Dhaka jobs; keep lunch/dinner auto-delivery lines; do **not** edit deploy YAML

## 6. Tests & docs (backend)

- [x] 6.1 Tests: threshold ordering on settings; reminder once/day; meal-stop blocks auto-delivery but allows admin mark; resume on recharge/cron; dry-run mutates nothing
- [x] 6.2 Tests: admin summary recipient path (mail outbox); batch continues after one notification failure; installer `bash -n` smoke where available
- [x] 6.3 Write `orders/docs/backend/wallet-balance-thresholds.md` (thresholds, cron, notifications, admin report, rollback notes)

## 7. Admin frontend (`F:\befood\befood-frontend`)

- [x] 7.1 Extend `orderWalletSettingsTypes` + `adminOrderWalletSettingsApi` for the two new fields
- [x] 7.2 Update `AdminSettingsPage` with labeled inputs for subscription / reminder / meal-stop thresholds and client-side ordering validation
- [x] 7.3 Verify verified-admin-only access still gates the settings form; add a short frontend note if the repo has a docs convention for admin settings
