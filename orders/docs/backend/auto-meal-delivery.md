# Auto Meal Delivery (Cron)

## Quick summary

Twice a day, production cron marks **eligible** `OrderDelivery` slots as `delivered` using the **same** domain path as the admin **Delivered** button (`mark_delivery` → wallet charge → Onahar). A best-effort FCM notify runs after a real transition to `delivered` (manual admin mark and cron share `mark_delivery_and_notify`).

| Job | Business time (`Asia/Dhaka`) | Crontab (UTC) | Command |
|-----|------------------------------|---------------|---------|
| Lunch | 15:00 | `0 9 * * *` | `auto_deliver_meals --meal-period lunch` |
| Dinner | 23:00 | `0 17 * * *` | `auto_deliver_meals --meal-period dinner` |

**Timezone layers (production):** EC2 host = UTC (`Etc/UTC`). Ubuntu cron evaluates minute/hour in UTC. Business “today” / product times stay Asia/Dhaka inside Django. **`CRON_TZ` is intentionally not used** — schedules are hard-converted BD → UTC in `install_managed_cron.sh`.

Wrappers: `scripts/cron/run_auto_deliver.sh lunch|dinner`  
Installer: `scripts/cron/install_managed_cron.sh` (idempotent tagged crontab block)

Deploy (`.github/workflows/deploy.yml`) syncs the server with `git fetch` + `git reset --hard origin/main` (discards dirty tracked files such as local cron edits; keeps untracked `.env` / logs), then runs `install_managed_cron.sh` when present.

## Shared helpers (reuse — do not duplicate)

| Concern | Module |
|---------|--------|
| Mark + charge + Onahar | `orders.services.order_delivery.mark_delivery` |
| Mark + notify | `orders.services.order_delivery.mark_delivery_and_notify` |
| Wallet debit | `orders.services.meal_payment.charge_delivered_meal` (via mark) |
| Live parents | `orders.services.subscription_parent.live_delivery_q` |
| Business “today” / TZ | `orders.services.meal_off.meal_off_business_now` / `MealOffSettings` |
| Batch runner | `orders.services.auto_meal_delivery.run_auto_delivery` |
| Push | `notifications.services.meal_delivery_notifications.notify_meal_delivered` |

## Eligibility

A slot is auto-delivered when **all** of:

1. `service_date` = target business date (default: meal-off timezone today)
2. `meal_period` = `lunch` or `dinner` (job-specific)
3. `status` = `scheduled` (customer meal-off / admin skip → `skipped` → **excluded**)
4. Parent is live per `live_delivery_q(service_date)` (non-cancelled order, active subscription, or cancelled-but-still-serving subscription)

Meal-off **deadlines** (`MealOffSettings`, default lunch previous-day 23:59 / dinner same-day 14:00) only gate the customer meal-off API. Cron does **not** re-check “before 03:00”; by 15:00/23:00 under defaults the off window is already closed. Ops can change deadlines via admin meal-off settings without changing cron code.

## Settings

| Setting | Default | Meaning |
|---------|---------|---------|
| `AUTO_MEAL_DELIVERY_ENABLED` | `True` | When `False`, command/service no-ops |
| `MEAL_DELIVERY_WALLET_CHARGE_ENABLED` | `True` | Existing wallet charge gate inside mark path |

## Management command

```bash
python manage.py auto_deliver_meals --meal-period lunch
python manage.py auto_deliver_meals --meal-period dinner --date 2026-09-03
python manage.py auto_deliver_meals --meal-period lunch --dry-run
python manage.py auto_deliver_meals --meal-period lunch --no-lock   # tests / emergency
```

Stdout summary includes candidate / delivered / failed counts. Per-slot wallet failures (`WALLET_INSUFFICIENT_FOR_MEAL`, `MEAL_SLOT_PRICE_MISSING`, …) are logged and **do not** abort the batch; those slots stay `scheduled` for admin retry.

Process lock: `tmp/locks/auto_deliver_{period}.lock` (Python) + optional `flock` in the shell wrapper.

## Managed cron install / verify / rollback

### Production layout

```text
/home/ubuntu/
├── befood-backend/     # PROJECT_DIR (manage.py, scripts/cron/)
└── venv/               # sibling venv — NOT under the project
```

Wrappers source `scripts/cron/_cron_env.sh`, which picks an absolute Python in this order: `BEFOOD_VENV` / `VENV_PATH` → sibling `../venv` → `PROJECT_DIR/venv` → `PROJECT_DIR/.venv`. Cron must not depend on PATH for `python`. For local runs against a non-prod settings module: `DJANGO_ENV=local bash scripts/cron/run_auto_deliver.sh lunch`.

### Install (also runs on deploy)

```bash
bash scripts/cron/install_managed_cron.sh
crontab -l
# Expect managed block like:
#   # BEGIN BEFOOD-MANAGED
#   # Host cron timezone: UTC
#   # Business timezone: Asia/Dhaka
#   0 9 * * *  .../run_auto_deliver.sh lunch
#   0 17 * * * .../run_auto_deliver.sh dinner
#   0 2 * * *  .../run_wallet_threshold_check.sh
#   0 14 * * * .../run_wallet_threshold_check.sh
#   # END BEFOOD-MANAGED
# Must NOT contain CRON_TZ=Asia/Dhaka or BD-hour fields (15/23/8/20).
```

Re-running the installer **replaces** the managed block (no duplicate lines; old `CRON_TZ` / BD hours are stripped).

### Verify

Shell scripts under `scripts/cron/` MUST use LF line endings (enforced by root `.gitattributes`: `*.sh text eol=lf`). CRLF breaks Linux deploy (`set: pipefail: invalid option name`).

```bash
bash -n scripts/cron/install_managed_cron.sh
bash -n scripts/cron/_cron_env.sh
bash -n scripts/cron/run_auto_deliver.sh
bash -n scripts/cron/run_wallet_threshold_check.sh
# no CR characters:
grep -r $'\r' scripts/cron/ && echo "CRLF found" || echo "LF OK"

bash scripts/cron/run_auto_deliver.sh lunch
tail -f logs/cron-auto-deliver-lunch.log

python manage.py auto_deliver_meals --meal-period lunch --dry-run
```

### Post-deploy production checks

```bash
cd /home/ubuntu/befood-backend
git status                          # expect clean tracked tree
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" && echo "HEAD matches origin/main"
crontab -l | sed -n '/# BEGIN BEFOOD-MANAGED/,/# END BEFOOD-MANAGED/p'
test -f .env && echo ".env present"
bash scripts/cron/run_auto_deliver.sh lunch
tail -n 50 logs/cron-auto-deliver-lunch.log
```

### Rollback

1. Remove managed block: edit crontab and delete from `# BEGIN BEFOOD-MANAGED` through `# END BEFOOD-MANAGED`, **or** re-install from a commit that empties the block.
2. Or set `AUTO_MEAL_DELIVERY_ENABLED=False` and leave crontab in place (jobs no-op).
3. No DB migration to reverse.

## Admin frontend behaviour (no FE change required)

Page: `/admin/subscriptions/:subscriptionId`  
Board: `/admin/delivery`

- Manual **Delivered** already calls `POST /api/v1/web/subscriptions/{id}/deliveries/{id}/mark`.
- After cron, slots show `delivered` (+ charged amount when present). **Delivered/Skip** controls only render for `status === 'scheduled'`, so buttons disappear on next refetch (React Query on window focus; no polling).
- Stale open page: clicking Delivered on an already-delivered slot → 409 / idempotent handling → cache invalidate.
- There is **no** meal-level `isVerified` on this page; that term usually means admin account or email verification elsewhere.

### Optional follow-up (not in this change)

Expose `marked_at` / note / “system vs admin” badge on subscription detail so ops can see cron marks. Types today omit `marked_by` on the admin detail payload.

## Failure modes

| Case | Result |
|------|--------|
| Insufficient wallet / frozen / missing slot price | Slot stays `scheduled`; failure counted; other slots continue |
| Overlapping cron | Lock busy → exit without double work (`mark_delivery` also idempotent) |
| FCM down / no tokens | Delivery + charge keep; notify logged and skipped |
| Feature flag off | No mutations |

## How to verify (automated)

See `orders/tests/test_auto_meal_delivery.py`.
