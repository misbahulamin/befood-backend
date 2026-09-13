## Why

Production `https://api.befood.com.bd/` intermittently returns **502 Bad Gateway** (nginx/1.28.3), including `/admin/`, with higher suspected correlation around lunch/dinner auto-delivery cron (`15:00` / `23:00` Asia/Dhaka). We do not yet know whether Gunicorn is unavailable, workers are timing out, OOM is killing processes, Postgres lock contention is stalling requests, cron is overlapping, or the timing is coincidence. Shipping a fix without log/config evidence risks the wrong change and further outages.

## What Changes

- Add a **read-only Phase 1 investigation plan** grounded in this repo’s auto-delivery / cron / deploy architecture (no production code, config, service, DB, or package mutations in Phase 1).
- Document exact call paths, lock behavior, sync external I/O, and known production process model (Nginx → unix socket `app.sock` → Supervisor `guni:*` → Gunicorn → Django; cron via Ubuntu crontab, not Celery).
- Provide **copy-paste safe evidence-collection commands** for Nginx, Gunicorn/Supervisor, OOM, cron logs, processes, and PostgreSQL, with Asia/Dhaka ↔ UTC window mapping for `14:55–15:10` and `22:55–23:10`.
- Require a **causal-chain verdict** (confirmed / refuted / inconclusive) before any remediation work.
- **Defer** production remediations (timeouts, batching, async notify, worker sizing, cron changes) to a follow-up change gated on Phase 1 evidence. No **BREAKING** API or product contract changes in this investigation change.

## Capabilities

### New Capabilities

- `production-502-investigation`: Read-only root-cause investigation for intermittent production 502s correlated with auto-meal-delivery cron — architecture map, log correlation timeline, safe evidence commands, and evidence-gated verdict before any fix.

### Modified Capabilities

- (none) — product specs for auto-delivery / wallet charge are unchanged until evidence justifies a follow-up change.

## Impact

- **In scope (docs / planning only for Phase 1):**
  - Cron: `scripts/cron/run_auto_deliver.sh`, `run_wallet_threshold_check.sh`, `_cron_env.sh`, `install_managed_cron.sh`
  - Command/service: `orders.management.commands.auto_deliver_meals`, `orders.services.auto_meal_delivery.run_auto_delivery`
  - Mark/charge path: `orders.services.order_delivery.mark_delivery` / `mark_delivery_and_notify`, `orders.services.meal_payment.charge_delivered_meal`, `wallet.services.ledger.debit_wallet`
  - Sync side effects per slot: Onahar credit, referral commission, inbox + FCM (`notifications.services.meal_delivery_notifications.notify_meal_delivered`)
  - Runtime (host, not fully in repo): Nginx → `/home/ubuntu/befood-backend/app.sock`, Supervisor program group `guni:*` (see `.github/workflows/deploy.yml`)
  - DB: production settings use **PostgreSQL** (`core.settings.prod.DATABASES`, RDS) — not SQLite
- **Out of scope for Phase 1:** code fixes, gunicorn/nginx config edits, restarts, kills, migrations, package installs, destructive commands, assumption-as-root-cause.
- **Follow-up (Phase 2+, separate apply after verdict):** only after written evidence names the failing layer.
