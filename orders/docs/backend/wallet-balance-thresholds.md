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
3. Reminder at most once per Asia/Dhaka business day.
4. Meal-stop notify primarily on transition to blocked.
5. Auto-delivery eligibility excludes blocked customers; **admin mark-delivery still works**.
6. Auto-resume when `balance ≥ meal_stop_threshold` (cron and successful `credit_wallet`).
7. Admin summary always runs after non-dry-run (including empty “no low-balance users” mail).

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
| Schedule | 08:00 and 20:00 Asia/Dhaka |
| Command | `python manage.py check_wallet_balance_thresholds [--dry-run] [--date YYYY-MM-DD]` |
| Wrapper | `scripts/cron/run_wallet_threshold_check.sh` |
| Shared env | `scripts/cron/_cron_env.sh` (absolute venv Python; sibling `/home/ubuntu/venv` on production) |
| Log | `logs/cron-wallet-threshold-check.log` |
| Install | `scripts/cron/install_managed_cron.sh` (also keeps lunch/dinner auto-deliver) |

**Production layout:** `/home/ubuntu/befood-backend` + sibling `/home/ubuntu/venv`. Wrappers must not rely on cron PATH for `python`.

Deploy syncs with `git fetch` + `git reset --hard origin/main` (discards dirty tracked files; keeps untracked `.env` / logs), then runs `install_managed_cron.sh` when present.

### Dry-run

```bash
python manage.py check_wallet_balance_thresholds --dry-run
```

Reports would-be remind/stop/resume counts without mutating state or sending mail/push.

## Notifications

| Event | Push `data.type` | Customer email templates |
|-------|------------------|--------------------------|
| Reminder | `wallet_low_balance` | `emails/wallet_low_balance_reminder_*` |
| Meal stop | `wallet_meal_stop` | `emails/wallet_meal_stop_*` |

Admin report recipients: same resolution as wallet funding (`resolve_funding_admin_emails`). HTML table columns: Name, Phone, Package, Current Balance, Address, Status (`Low Balance` / `Meal Stopped`).

## Rollback notes

1. Revert managed crontab by restoring previous `install_managed_cron.sh` and re-running it (or remove wallet lines from the managed block).
2. Clear blocks: set `CustomerProfile.meal_service_blocked_low_balance=False` for affected users.
3. Threshold fields can remain unused if cron is disabled.

## How to verify

- `orders.tests.test_order_eligibility.OrderWalletEligibilityTests` — settings ordering / defaults
- `orders.tests.test_wallet_balance_thresholds.WalletBalanceThresholdTests` — reminder, stop, resume, admin mail, dry-run
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
