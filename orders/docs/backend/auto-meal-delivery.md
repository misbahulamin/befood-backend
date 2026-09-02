# Auto Meal Delivery (Cron)

## Quick summary

Twice a day, production cron marks **eligible** `OrderDelivery` slots as `delivered` using the **same** domain path as the admin **Delivered** button (`mark_delivery` → wallet charge → Onahar). A best-effort FCM notify runs after a real transition to `delivered` (manual admin mark and cron share `mark_delivery_and_notify`).

| Job | Local time (`Asia/Dhaka`) | Command |
|-----|---------------------------|---------|
| Lunch | 15:00 | `python manage.py auto_deliver_meals --meal-period lunch` |
| Dinner | 23:00 | `python manage.py auto_deliver_meals --meal-period dinner` |

Wrappers: `scripts/cron/run_auto_deliver.sh lunch|dinner`  
Installer: `scripts/cron/install_managed_cron.sh` (idempotent tagged crontab block)

**Do not edit** `.github/workflows/deploy.yml`. Deploy already runs the installer when that script exists.

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

### Install (also runs on deploy)

```bash
bash scripts/cron/install_managed_cron.sh
crontab -l   # expect BEGIN/END BEFOOD-MANAGED block, CRON_TZ=Asia/Dhaka, 15:00 lunch, 23:00 dinner
```

Re-running the installer **replaces** the managed block (no duplicate lines).

### Verify

```bash
bash -n scripts/cron/install_managed_cron.sh
bash -n scripts/cron/run_auto_deliver.sh
python manage.py auto_deliver_meals --meal-period lunch --dry-run
tail -f logs/cron-auto-deliver-lunch.log
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
