## ADDED Requirements

### Requirement: Phase 1 investigation is read-only on production

The investigation MUST NOT modify production application code, Nginx/Gunicorn/Supervisor configuration, crontab contents, database schema or data, installed packages, or running services during Phase 1. Operators MUST collect evidence using read-only status, log, process, and query commands only. Destructive or mutating actions (restart, kill, stop, migrate, install, truncate, write SQL, config edits) MUST be deferred until a follow-up change after a written root-cause verdict.

#### Scenario: Operator follows Phase 1 checklist

- **WHEN** an operator executes the Phase 1 evidence-collection procedure on the production host
- **THEN** every listed command is read-only and the procedure does not instruct service restarts, process kills, package installs, migrations, or configuration writes

#### Scenario: Remediations are gated

- **WHEN** a suspected fix (timeout, worker count, async notify, batching, cron change) is proposed
- **THEN** the investigation artifacts MUST require a completed root-cause verdict classifying the incident as confirmed, refuted, timing coincidence, or inconclusive before any production mutation is authorized in a separate change

### Requirement: Architecture map cites exact repo paths

The investigation MUST document the production auto-delivery path with exact file paths and symbols: cron wrapper `scripts/cron/run_auto_deliver.sh`, installer `scripts/cron/install_managed_cron.sh`, shared env `scripts/cron/_cron_env.sh`, management command `orders.management.commands.auto_deliver_meals`, batch service `orders.services.auto_meal_delivery.run_auto_delivery`, mark path `orders.services.order_delivery.mark_delivery` / `mark_delivery_and_notify`, wallet charge `orders.services.meal_payment.charge_delivered_meal`, and sync notify `notifications.services.meal_delivery_notifications.notify_meal_delivered`. The map MUST state that 15:00/23:00 Asia/Dhaka jobs process existing scheduled `OrderDelivery` rows and do not create subscription delivery slots.

#### Scenario: Reader can trace cron to wallet debit

- **WHEN** a reader opens the investigation architecture map
- **THEN** they can follow crontab → shell wrapper → `auto_deliver_meals` → `run_auto_delivery` → `mark_delivery_and_notify` → `charge_delivered_meal` / `debit_wallet` with named modules and understand that slots are pre-created elsewhere

### Requirement: Cron schedule and lock behavior are recorded

The investigation MUST record managed cron schedules in both UTC (host crontab) and Asia/Dhaka business time for lunch auto-deliver, dinner auto-deliver, and both wallet-threshold runs. It MUST document duplicate-run protections (`flock` in the shell wrapper when available, Python `fcntl` process lock under `tmp/locks/auto_deliver_{period}.lock`, domain idempotency) and MUST verify on the host whether managed crontab lines are duplicated or installed under more than one user.

#### Scenario: Schedule conversion is explicit

- **WHEN** investigators correlate logs around lunch or dinner
- **THEN** they use lunch `15:00` Asia/Dhaka = `09:00` UTC and dinner `23:00` Asia/Dhaka = `17:00` UTC as documented by `install_managed_cron.sh`

#### Scenario: Lock busy is distinguishable from a full run

- **WHEN** cron-auto-deliver logs contain `lock busy` or the command reports `lock_busy`
- **THEN** investigators treat that as overlapping protection, not as proof that work completed, and still check whether another process held the lock for a long duration

### Requirement: Nginx 502 class is identified from upstream errors

The investigation MUST NOT treat HTTP 502 as a generic Django application error. Investigators MUST locate the Nginx → Gunicorn upstream (expected unix socket `/home/ubuntu/befood-backend/app.sock` per deploy workflow) and classify the Nginx error class among at least: connection refused, missing socket path, upstream prematurely closed, connection reset by peer, upstream timed out, or invalid upstream response. Each classification MUST cite log evidence paths (for example `/var/log/nginx/error.log` and Supervisor/Gunicorn logs).

#### Scenario: Socket missing versus worker timeout

- **WHEN** Nginx logs `No such file or directory` for the upstream socket during a 502 window
- **THEN** the investigation records Gunicorn/Supervisor down or socket path mismatch as the leading hypothesis rather than an application validation error

#### Scenario: Premature close points at worker death

- **WHEN** Nginx logs `upstream prematurely closed connection` aligned with Gunicorn worker timeout or exit lines
- **THEN** the investigation records worker death/timeout as a leading hypothesis and continues OOM and exception correlation

### Requirement: Incident timeline correlates cron and 502 windows

For each investigated incident, the investigation MUST build a timeline covering approximately `14:55–15:10` and/or `22:55–23:10` Asia/Dhaka (and equivalent UTC) that records cron start, deliveries processed counts when available, cron errors, Gunicorn events, Nginx upstream errors, OOM evidence, database errors if available, 502 start, 502 end, and cron finish. The written verdict MUST state whether the causal chain cron → resource/DB/application problem → Gunicorn unavailable → Nginx 502 is confirmed, refuted, only timing coincidence, or inconclusive.

#### Scenario: Confirmed causal chain

- **WHEN** cron start precedes resource or process failure which precedes Gunicorn unavailability which precedes Nginx 502, with matching timestamps and no contradictory healthier signal
- **THEN** the verdict is recorded as confirmed causal with cited evidence lines

#### Scenario: Timing coincidence only

- **WHEN** cron and 502 overlap in time but Nginx/Gunicorn/OOM/DB evidence shows an unrelated failure mode or 502s also occur with the same signature far outside cron windows without cron activity
- **THEN** the verdict MUST NOT claim cron as root cause and MUST label the overlap as coincidence or point to the evidenced layer instead

### Requirement: Production database engine drives lock analysis

The investigation MUST determine the production database engine from Django settings (production uses PostgreSQL) and MUST NOT apply SQLite-specific lock guidance as production truth. Database checks in Phase 1 MUST be read-only (for example `pg_stat_activity` / `pg_locks` inspection when accessible) and MUST look for connection exhaustion, long transactions, and blocking locks around auto-delivery windows when credentials/access allow.

#### Scenario: Engine is PostgreSQL

- **WHEN** investigators inspect production `DATABASES['default']['ENGINE']`
- **THEN** they record `django.db.backends.postgresql` and use PostgreSQL-oriented read-only diagnostics rather than SQLite `database is locked` assumptions

### Requirement: Sync per-slot side effects are evaluated as load factors

The investigation MUST evaluate whether synchronous per-delivery work in `run_auto_delivery` (row locks, wallet debit, meal-stop evaluation, Onahar credit, referral commission, inbox create, FCM `send_to_tokens`) can prolong the cron process and contend with web workers for CPU, RAM, or database locks. Code review findings MUST be labeled as risk factors until runtime metrics or logs confirm impact on Gunicorn availability.

#### Scenario: Code risk without runtime proof

- **WHEN** code review shows synchronous FCM inside the auto-delivery loop
- **THEN** the investigation documents it as a potential amplifier of cron duration and resource use but does not declare it the 502 root cause without correlating runtime evidence
