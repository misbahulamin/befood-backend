## Context

Production stack (from repo + deploy workflow; host configs are **not** fully checked into git):

| Layer | Evidence in repo |
|-------|------------------|
| Public URL | `api.befood.com.bd` (`core/settings/prod.py` `ALLOWED_HOSTS`) |
| Reverse proxy | Nginx (`sudo nginx -t` / `systemctl reload nginx` in `.github/workflows/deploy.yml`) |
| App process | Supervisor group `guni:*` restarted via `supervisorctl restart 'guni:*'` |
| Upstream | Unix socket `/home/ubuntu/befood-backend/app.sock` (`test -S "$PROJECT_DIR/app.sock"`; curl over `--unix-socket`) |
| App | Django WSGI behind Gunicorn (service unit/conf live on host under Supervisor) |
| Cron | Ubuntu crontab installed by `scripts/cron/install_managed_cron.sh` (UTC schedules) |
| Jobs | Auto-deliver lunch/dinner; wallet threshold 08:00/20:00 Asia/Dhaka |
| DB | PostgreSQL on RDS (`django.db.backends.postgresql` in `core/settings/prod.py`) |
| Celery | **Not** used for this flow |

Observed symptom: intermittent **502 Bad Gateway** from nginx, suspected around auto-delivery windows. Phase 1 must prove or refute a causal chain with logs — not assumptions.

### Repo architecture map (Phase 1 code facts)

```text
crontab (UTC)
  0 9  * * *  run_auto_deliver.sh lunch     → 15:00 Asia/Dhaka
  0 17 * * *  run_auto_deliver.sh dinner    → 23:00 Asia/Dhaka
  0 2  * * *  run_wallet_threshold_check.sh → 08:00 Asia/Dhaka
  0 14 * * *  run_wallet_threshold_check.sh → 20:00 Asia/Dhaka
        │
        ▼
_cron_env.sh → absolute PYTHON_BIN (sibling ../venv preferred)
        │
        ▼
manage.py auto_deliver_meals --meal-period {lunch|dinner}
        │
        ▼
orders.services.auto_meal_delivery.run_auto_delivery
  • flock wrapper lock: tmp/locks/cron-wrapper-auto-deliver-{period}.lock
  • Python lock: tmp/locks/auto_deliver_{period}.lock (fcntl LOCK_EX|LOCK_NB)
  • Materialize PKs: list(qs.values_list('id', flat=True))  # IDs only, not full rows
  • Per id: reload row → mark_delivery_and_notify(...)
        │
        ▼
orders.services.order_delivery.mark_delivery  (@transaction.atomic)
  • select_for_update(of=('self',)) on OrderDelivery
  • charge_delivered_meal → debit_wallet (Wallet select_for_update)
  • evaluate_meal_stop_after_debit (post-debit; may notify on_commit)
  • credit_for_delivery (Onahar; exceptions swallowed)
  • referral commission helpers (exceptions swallowed)
        │
        ▼
mark_delivery_and_notify (AFTER atomic commit)
  • notify_meal_delivered — SYNC inbox + FCM send_to_tokens (best-effort, no raise)
```

**Important:** 15:00/23:00 jobs do **not** create slots; they process existing `scheduled` `OrderDelivery` rows.

### Duplicate / parallel protection (code)

| Layer | Mechanism | Failure mode |
|-------|-----------|--------------|
| Shell | `flock -n 9` on wrapper lock (if `flock` exists) | Logs `lock busy`; exit 0 |
| Python | `auto_delivery_process_lock` via `fcntl.flock` NB | `lock_busy`; command may exit with `CommandError` |
| Domain | `mark_delivery` idempotent same status; wallet idempotency key | Safe re-mark / no double charge |

If `flock` binary is missing, shell lock is skipped but Python lock still applies. Installer replaces `# BEGIN BEFOOD-MANAGED` … `# END BEFOOD-MANAGED` so duplicate managed lines should not accumulate from reinstall; **manual duplicate crontab entries outside the block remain possible** — verify on host.

### Why cron *can* stress the web tier (hypotheses — unconfirmed)

Per eligible slot, auto-delivery runs **synchronously** in one long-lived `manage.py` process: DB transactions with row locks, wallet debit, optional meal-stop, Onahar, referrals, then **blocking FCM**. That process shares the **same PostgreSQL** with Gunicorn workers. Possible (not proven) 502 mechanisms:

1. Worker timeout / crash → Nginx `upstream prematurely closed` / connect fail to `app.sock`
2. OOM killer → Gunicorn master/workers gone → socket missing / connection refused
3. All workers blocked on DB locks / slow queries → Nginx read timeout (if configured) or socket backlog
4. Supervisor restart during deploy coinciding with cron
5. Unrelated infra (disk full, RDS CPU, network)

Phase 1 must distinguish these via Nginx error strings + Gunicorn/Supervisor + kernel OOM + cron log timing.

## Goals / Non-Goals

**Goals:**

- Produce a written root-cause verdict with cited evidence (log lines, timestamps, process names).
- Map exact code/config paths for auto-delivery and production process model.
- Give operators **read-only** copy-paste commands for incident windows.
- Correlate cron start/finish with 502 start/end in Asia/Dhaka and UTC.
- Gate any remediation on that verdict.

**Non-Goals:**

- Phase 1 production mutations (code deploy for “fix”, nginx/gunicorn edits, restarts, kills, migrate, package install).
- Replacing cron with Celery in this change.
- Changing auto-delivery product eligibility or wallet rules.
- Assuming cron is the cause without correlation.

## Decisions

### 1. Investigation-first, fix-later

**Decision:** This OpenSpec change’s apply work is investigation artifacts + (optional) offline analysis docs in-repo; remediations are a **separate** change after verdict.

**Rationale:** User safety rule; wrong timeout/worker tweak can mask OOM or worsen lock contention.

**Alternatives considered:** Immediate “raise gunicorn timeout” / “move FCM async” — rejected until evidence names the failing layer.

### 2. Evidence sources of truth

**Decision:** Prefer live host logs over repo assumptions for Nginx/Gunicorn config. Repo only proves: socket path `app.sock`, Supervisor `guni:*`, cron scripts, Django call graph, PostgreSQL engine.

**Rationale:** Gunicorn/nginx conf files are host-managed (not found in repo root).

### 3. Time windows

**Decision:** Correlate in both Asia/Dhaka and UTC:

| Asia/Dhaka | UTC (host cron / typical journal) |
|------------|-----------------------------------|
| 14:55–15:10 | 08:55–09:10 |
| 22:55–23:10 | 16:55–17:10 |

Cron fire times: lunch `09:00 UTC`, dinner `17:00 UTC`.

### 4. Verdict taxonomy

**Decision:** Final report MUST classify:

- **Confirmed causal:** cron → resource/DB/app failure → Gunicorn unavailable → Nginx 502 (with timestamps)
- **Refuted:** 502 outside cron / no cron overlap / different root layer
- **Timing coincidence:** overlap without mechanism evidence
- **Inconclusive:** missing logs / retention / no incident during observation

### 5. Safe command policy

**Decision:** Commands in tasks/docs for Phase 1 are read-only (`status`, `journalctl`, `grep`/`rg` on logs, `crontab -l`, `ps`, `free`, `df`, `SELECT`/`pg_stat_*` read queries). Explicitly forbid `restart`, `kill`, `systemctl stop`, `truncate`, `VACUUM FULL`, DDL, and write SQL.

## Risks / Trade-offs

- **[Risk] Log retention too short** → Mitigation: capture ASAP after next 15:00/23:00; note gaps honestly as inconclusive.
- **[Risk] Operator runs a mutating command by mistake** → Mitigation: commands documented with `# READ-ONLY` headers; no “fix” section until Phase 2.
- **[Risk] Secrets in `prod.py` / `.env` leak into investigation notes** → Mitigation: never paste DB passwords, tokens, or full `.env` into artifacts; refer to engine/host only.
- **[Risk] False attribution to cron** → Mitigation: require Nginx upstream error class + Gunicorn event within ±window of cron, or declare coincidence.
- **[Risk] Sync FCM looks “guilty” in code review but is not the 502 cause** → Mitigation: measure duration and worker/OOM evidence; code smell ≠ production root cause.
- **[Trade-off] Deep DB lock analysis needs RDS credentials / `psql`** → Prefer read-only views; if access limited, mark DB contention inconclusive.

## Migration Plan

Not a product migration. Operational sequence:

1. **Phase 1a (repo):** Complete this change’s investigation doc/tasks (architecture map already started here).
2. **Phase 1b (host, read-only):** Operator runs safe commands during/after next lunch or dinner window; paste redacted evidence into investigation notes.
3. **Verdict:** Confirm / refute / coincidence / inconclusive.
4. **Phase 2 (new OpenSpec change):** Only then implement remediations (e.g. async notify, batching, timeout/worker tuning, lock/contention fixes) with tests and deploy plan.
5. **Rollback:** N/A for Phase 1 (no deploy). Phase 2 rollback defined in that future change.

## Open Questions

1. Exact Supervisor program conf path and Gunicorn CLI (`workers`, `timeout`, `bind=unix:...`)? (discover on host)
2. Exact Nginx site file for `api.befood.com.bd` and `proxy_read_timeout` / `proxy_connect_timeout`?
3. Cron runs as which user (`ubuntu` crontab vs root)? (`crontab -l` vs `sudo crontab -l`)
4. Typical candidate count at lunch/dinner (order of magnitude)?
5. Do 502s also occur far from 15:00/23:00 with the same Nginx error class?
6. Is Daphne/ASGI also on this host for `/ws/` and could it share RAM pressure?

---

## Appendix A — Nginx 502 error classes → evidence

| Symptom (error.log) | Likely meaning | Where to look |
|---------------------|----------------|---------------|
| `connect() failed (111: Connection refused)` to upstream | Nothing listening on socket/port | `app.sock` exists? `supervisorctl status`; Gunicorn down |
| `connect() ... No such file or directory` | Socket path missing | Socket deleted during restart/crash |
| `upstream prematurely closed connection` | Worker died mid-request | Gunicorn worker timeout/crash logs |
| `Connection reset by peer` | Upstream reset | Worker kill / OOM |
| `upstream timed out` | Slow app / blocked workers | DB locks, sync I/O, too few workers |
| `upstream sent too big header` / invalid response | App/protocol issue (less common for wholesale admin 502) | Gunicorn access/error |

Repo proves socket path expectation: `$PROJECT_DIR/app.sock` with `PROJECT_DIR=/home/ubuntu/befood-backend`.

## Appendix B — Safe production commands (Phase 1)

All commands below are **READ-ONLY**. Do not restart services.

### Time helpers

```bash
# Confirm host TZ and convert windows
timedatectl
date -u
TZ=Asia/Dhaka date

# Lunch window UTC = 08:55–09:10 ; Dinner UTC = 16:55–17:10
```

### A. Nginx

```bash
# READ-ONLY
systemctl status nginx --no-pager
nginx -T 2>/dev/null | sed -n '/server_name.*api.befood.com.bd/,/^}/p' | head -n 200
# If sed block incomplete, locate site:
ls -la /etc/nginx/sites-enabled/
grep -R "api.befood.com.bd\|proxy_pass\|app.sock\|proxy_read_timeout\|proxy_connect_timeout\|upstream" /etc/nginx/ -n --include='*.conf' 2>/dev/null | head -n 100

# Recent errors
sudo tail -n 200 /var/log/nginx/error.log
sudo grep -E '502|upstream|connect\\(\\)|reset by peer|prematurely closed|timed out' /var/log/nginx/error.log | tail -n 100

# Lunch window (UTC) — adjust if log uses local time
sudo awk '/08:5[5-9]|09:0|09:10/' /var/log/nginx/error.log | tail -n 200
# Dinner window
sudo awk '/16:5[5-9]|17:0|17:10/' /var/log/nginx/error.log | tail -n 200

# journal (if nginx logs there)
sudo journalctl -u nginx --since "today" --no-pager | tail -n 200
```

### B. Gunicorn / Supervisor

```bash
# READ-ONLY — discover service name
sudo supervisorctl status
ls -la /etc/supervisor/conf.d/ 2>/dev/null
sudo grep -R "gunicorn\\|app.sock\\|guni" /etc/supervisor/ -n 2>/dev/null | head -n 80

# Status + recent program logs (paths from conf; common patterns)
sudo supervisorctl tail guni: 2>/dev/null || true
# If programs are named like guni:gunicorn_00, try:
sudo supervisorctl status guni:*

# Search logs (adjust path after discovering logfile= in supervisor conf)
sudo grep -Eih 'TIMEOUT|WORKER TIMEOUT|Worker exiting|Booting worker|SIGKILL|Killed|Exception|Traceback|CRITICAL' \
  /var/log/supervisor/* /home/ubuntu/befood-backend/logs/* 2>/dev/null | tail -n 200

# Socket
ls -la /home/ubuntu/befood-backend/app.sock
```

Also check systemd only if present (deploy uses Supervisor primarily):

```bash
systemctl list-units --type=service --all | grep -Ei 'gunicorn|befood|daphne' || true
```

### C. OOM / RAM / disk

```bash
# READ-ONLY
free -h
swapon --show
uptime
df -h
df -i
sudo journalctl -k --since "7 days ago" --no-pager | grep -Ei 'oom|Out of memory|Killed process|gunicorn|python' | tail -n 100
sudo dmesg -T 2>/dev/null | grep -Ei 'oom|Out of memory|Killed process|gunicorn|python' | tail -n 50
```

### D. Cron

```bash
# READ-ONLY — which user owns managed cron?
crontab -l
sudo crontab -l 2>/dev/null || true
# Show managed block + detect duplicates of run_auto_deliver
crontab -l | sed -n '/# BEGIN BEFOOD-MANAGED/,/# END BEFOOD-MANAGED/p'
crontab -l | grep -n 'run_auto_deliver\|auto_deliver\|wallet_threshold' || true
sudo grep -E 'CRON|run_auto_deliver|auto_deliver' /var/log/syslog 2>/dev/null | tail -n 100
# Cron job app logs
ls -la /home/ubuntu/befood-backend/logs/
tail -n 100 /home/ubuntu/befood-backend/logs/cron-auto-deliver-lunch.log
tail -n 100 /home/ubuntu/befood-backend/logs/cron-auto-deliver-dinner.log
# Window greps (ISO timestamps from script: date -Is)
grep -E 'T14:5|T15:0|T15:1|lock busy|auto_deliver_meals|finished|ERROR' \
  /home/ubuntu/befood-backend/logs/cron-auto-deliver-lunch.log | tail -n 80
grep -E 'T22:5|T23:0|T23:1|lock busy|auto_deliver_meals|finished|ERROR' \
  /home/ubuntu/befood-backend/logs/cron-auto-deliver-dinner.log | tail -n 80
ls -la /home/ubuntu/befood-backend/tmp/locks/
```

### E. Processes (especially near :59–:05)

```bash
# READ-ONLY snapshot
ps aux | grep -E '[g]unicorn|[m]anage.py|[a]uto_deliver|[c]heck_wallet' 
ps -eo pid,ppid,user,%cpu,%mem,etime,cmd --sort=-%mem | head -n 40
pgrep -a -f 'auto_deliver_meals|check_wallet_balance' || echo 'no management command running'
```

### F. Database (PostgreSQL)

Confirm engine from settings (already: PostgreSQL). On host, prefer env/`manage.py` dbshell carefully — **read-only SQL only**:

```bash
# READ-ONLY — do not paste passwords into chat logs
cd /home/ubuntu/befood-backend
source /home/ubuntu/venv/bin/activate
export DJANGO_ENV=prod
# Inspect engine without printing secrets:
python -c "import django; django.setup(); from django.conf import settings; e=settings.DATABASES['default']; print(e['ENGINE'], e.get('HOST','?'), e.get('NAME','?'), e.get('PORT','?'))"

# If psql available with IAM/.pgpass already configured by ops:
# SELECT count(*) FROM pg_stat_activity;
# SELECT pid, usename, state, wait_event_type, wait_event, left(query,120), query_start
#   FROM pg_stat_activity WHERE datname = current_database() ORDER BY query_start NULLS LAST;
# SELECT * FROM pg_locks WHERE NOT granted LIMIT 50;
```

SQLite-specific checks do **not** apply to production.

## Appendix C — Correlation checklist (fill per incident)

| # | Event | Time (Asia/Dhaka) | Time (UTC) | Evidence source |
|---|-------|-------------------|------------|-----------------|
| 1 | Cron start line in `cron-auto-deliver-*.log` | | | |
| 2 | Candidate / delivered / failed counts | | | |
| 3 | Cron finish / last log line | | | |
| 4 | First Nginx 502 / upstream error | | | |
| 5 | Last Nginx 502 in burst | | | |
| 6 | Gunicorn worker timeout / exit / boot | | | |
| 7 | OOM kill line | | | |
| 8 | Supervisor FATAL / EXITED | | | |
| 9 | DB lock / connection errors | | | |
| 10 | Verdict | confirmed / refuted / coincidence / inconclusive | | |

## Appendix D — Code hotspots for Phase 1 analysis (no edits)

| Concern | Path |
|---------|------|
| Shell wrapper + flock + log | `scripts/cron/run_auto_deliver.sh` |
| Crontab install (UTC) | `scripts/cron/install_managed_cron.sh` |
| Venv / `DJANGO_ENV=prod` | `scripts/cron/_cron_env.sh` |
| Management command | `orders/management/commands/auto_deliver_meals.py` |
| Batch loop + locks | `orders/services/auto_meal_delivery.py` (`run_auto_delivery`, `auto_delivery_process_lock`) |
| Mark + charge + side effects | `orders/services/order_delivery.py` (`mark_delivery`, `mark_delivery_and_notify`) |
| Wallet debit | `orders/services/meal_payment.py` (`charge_delivered_meal`) → `wallet/services/ledger.py` (`debit_wallet`) |
| Sync push | `notifications/services/meal_delivery_notifications.py` (`notify_meal_delivered`) |
| Deploy process model | `.github/workflows/deploy.yml` (Supervisor `guni:*`, `app.sock`) |
| Prod DB engine | `core/settings/prod.py` |
