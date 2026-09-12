# Wallet Balance Thresholds

## Quick summary

Admins configure three ordered wallet thresholds. A twice-daily cron evaluates active subscribers, sends low-balance reminders, blocks automated meal delivery when balance is critically low, resumes when balance recovers, and emails verified admins a structured report.

| Threshold | Field | Default | Trigger |
|-----------|-------|---------|---------|
| Subscription minimum | `min_wallet_balance_to_order` | `500.00` | Subscribe requires `balance >=` this |
| Low-balance reminder | `low_balance_reminder_threshold` | `300.00` | Reminder when `balance <` this |
| Meal stop | `meal_stop_threshold` | `200.00` | Auto meal delivery blocked when `balance <` this |

**Ordering rule (strict):**  
`subscription minimum > low-balance reminder > meal stop ≥ 0`

## Permissions

| Actor | Capability |
|-------|------------|
| Verified admin | GET/PATCH `/api/v1/web/orders/order-wallet-settings/` |
| Verified customer | Read thresholds on `GET /wallet/` (cannot write) |
| Cron / ops | `manage.py check_wallet_balance_thresholds` |

## Key models

- `orders.OrderWalletSettings` (singleton `pk=1`) — three decimal fields + `updated_at`
- `user_management.CustomerProfile`:
  - `meal_service_blocked_low_balance`
  - `meal_service_blocked_at`
  - `last_low_balance_reminder_on` (Asia/Dhaka business date)

## Business rules

1. Subscribe gate unchanged: inclusive compare against `min_wallet_balance_to_order`.
2. Cron priority per customer: meal-stop → resume → reminder.
3. Reminder at most once per Asia/Dhaka business day (`last_low_balance_reminder_on`).
4. Meal-stop **block** when `balance < meal_stop_threshold` (unchanged).
5. **Post-meal-charge meal-stop (immediate):** after a **successful** meal-delivery wallet debit (`charge_delivered_meal` — auto-deliver or admin mark-delivered), `evaluate_meal_stop_after_debit` compares post-debit spendable balance to `meal_stop_threshold` and applies `meal_service_blocked_low_balance` when strictly below. Idempotent re-attach / charge-disabled paths do **not** re-evaluate. Newly blocked customers get meal-stop notify on `transaction.on_commit` (notify failure must not undo charge or block). This path does **not** resume, remind, or send the admin summary.
6. Meal-stop-band **push** (“Low Wallet Balance Alert”) on **every** non-dry-run cron evaluation while still below meal-stop — including already-blocked customers. **Not** gated by `last_low_balance_reminder_on` (with the twice-daily cron, about 2 pushes/day while under threshold).
7. Meal-stop **email** remains primarily on transition to newly blocked (push carries the every-run warning).
8. Auto-delivery eligibility excludes blocked customers; **admin mark-delivery still works**.
9. Auto-resume when `balance ≥ meal_stop_threshold`:
   - threshold cron
   - successful `credit_wallet` (`transaction.on_commit`)
   - admin `approve_recharge` (sync inside the same atomic; API field `meal_service_restored`)
   - **not** on the post-debit evaluate path
10. Admin summary always runs after non-dry-run (including empty “no low-balance users” mail).
11. **08:00 / 20:00 Asia/Dhaka cron remains required** for reminders, resume, admin summary, and customers who fall below threshold without a meal debit. Post-charge evaluation does **not** replace crontab schedules (no 15:05/23:05 cron required for this fix).
12. **No migration** for post-charge meal-stop, resume-on-approve, or every-run meal-stop push — existing profile fields only.

## Admin API

### GET / PATCH `/api/v1/web/orders/order-wallet-settings/`

Auth: verified admin (`IsVerifiedAdmin`).

**Response example:**

```json
{
  "min_wallet_balance_to_order": "500.00",
  "low_balance_reminder_threshold": "300.00",
  "meal_stop_threshold": "200.00",
  "updated_at": "2026-09-03T08:00:00Z"
}
```

**PATCH body (partial OK):**

```json
{
  "min_wallet_balance_to_order": "500.00",
  "low_balance_reminder_threshold": "300.00",
  "meal_stop_threshold": "200.00"
}
```

Ordering conflicts and negative / >2 decimal amounts return `400`.

## Customer wallet read

`GET /wallet/` includes the three threshold fields as read-only strings.

## Cron

| Item | Value |
|------|--------|
| Business schedule | 08:00 and 20:00 Asia/Dhaka |
| Crontab (UTC) | `0 2 * * *` and `0 14 * * *` |
| Command | `check_wallet_balance_thresholds [--dry-run] [--date YYYY-MM-DD]` |
| Wrapper | `scripts/cron/run_wallet_threshold_check.sh` |
| Shared env | `scripts/cron/_cron_env.sh` (absolute venv Python; sibling `/home/ubuntu/venv` on production) |
| Log | `logs/cron-wallet-threshold-check.log` |
| Install | `scripts/cron/install_managed_cron.sh` (also keeps lunch/dinner auto-deliver) |

**Timezone layers (production):** EC2 host = UTC (`Etc/UTC`). Crontab minute/hour fields are UTC (08:00 BD → 02:00 UTC, 20:00 BD → 14:00 UTC). Business dates inside the command remain Asia/Dhaka. **`CRON_TZ` is intentionally not used.**

**Production layout:** `/home/ubuntu/befood-backend` + sibling `/home/ubuntu/venv`. Wrappers must not call bare `python` — they log `PYTHON_BIN=/absolute/path`.

Deploy syncs with `git fetch` + `git reset --hard origin/main` (discards dirty tracked files; keeps untracked `.env` / logs), then runs `install_managed_cron.sh` when present.

### Dry-run

```bash
python manage.py check_wallet_balance_thresholds --dry-run
```

Reports would-be remind/stop/resume counts without mutating state or sending mail/push.

## Notifications

| Event | Push `data.type` | Customer email templates |
|-------|------------------|--------------------------|
| Reminder (reminder band, once/day) | `wallet_low_balance` | `emails/wallet_low_balance_reminder_*` |
| Meal-stop band warning (every cron while below meal-stop) | `wallet_meal_stop` | Email on newly blocked: `emails/wallet_meal_stop_*` |

**Meal-stop push copy:**

- Title: `Low Wallet Balance Alert`
- Body: `Hi {customer_full_name}, your current wallet balance is low. Please recharge your wallet soon to continue receiving your meals. If your balance remains low, your meal service will be paused.`

Spendable balance for all comparisons is `Wallet.balance` via `spendable_balance()` (same for cron, post-charge meal-stop, `credit_wallet` resume, and `approve_recharge` resume).

Admin report recipients: same resolution as wallet funding (`resolve_funding_admin_emails`). HTML table columns: Name, Phone, Package, Current Balance, Address, Status (`Low Balance` / `Meal Stopped`).

## Shared helpers

| Concern | Module |
|---------|--------|
| Cron batch | `orders.services.wallet_balance_thresholds.run_wallet_threshold_check` |
| Post-debit stop-only | `orders.services.wallet_balance_thresholds.evaluate_meal_stop_after_debit` |
| Block / clear | `apply_meal_service_block` / `clear_meal_service_block` |
| Resume on credit | `maybe_resume_after_wallet_credit` |

## Rollback notes

1. Revert managed crontab by restoring previous `install_managed_cron.sh` and re-running it (or remove wallet lines from the managed block).
2. Clear blocks: set `CustomerProfile.meal_service_blocked_low_balance=False` for affected users.
3. Threshold fields can remain unused if cron is disabled.

## How to verify

- `orders.tests.test_order_eligibility.OrderWalletEligibilityTests` — settings ordering / defaults
- `orders.tests.test_wallet_balance_thresholds.WalletBalanceThresholdTests` — reminder, stop, every-run meal-stop push, resume, admin mail, dry-run
- `orders.tests.test_meal_delivery_wallet_payment.PostMealChargeMealStopTests` — immediate block after meal debit, kitchen count, notify failure isolation
- `wallet.tests.test_meal_service_resume_on_approve` — approve resume + `meal_service_restored`
- `bash -n scripts/cron/install_managed_cron.sh scripts/cron/_cron_env.sh scripts/cron/run_wallet_threshold_check.sh`
- Confirm cron scripts are LF-only (`.gitattributes`: `*.sh text eol=lf`). `grep -r $'\r' scripts/cron/` should find nothing.
- Manual smoke on the server (or a host with sibling/local venv):

```bash
bash scripts/cron/run_wallet_threshold_check.sh
tail -n 50 logs/cron-wallet-threshold-check.log
```

- After landing on `main`, re-run production deploy; sync step should hard-reset to `origin/main`, then step 9 installs managed cron.
- Post-deploy on EC2:

```bash
cd /home/ubuntu/befood-backend
git status
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" && echo "HEAD matches origin/main"
crontab -l | sed -n '/# BEGIN BEFOOD-MANAGED/,/# END BEFOOD-MANAGED/p'
bash scripts/cron/run_wallet_threshold_check.sh
tail -n 50 logs/cron-wallet-threshold-check.log
test -f .env && echo ".env present"
```

- Remaining risks: host crontab permissions; a wrong/empty sibling `../venv` (override with `BEFOOD_VENV=/path/to/venv` if needed).
